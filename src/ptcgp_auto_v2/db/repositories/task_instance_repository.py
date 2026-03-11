# -*- coding: utf-8 -*-
from datetime import datetime
from typing import Any, List, Optional, cast

from sqlalchemy.orm import selectinload
from sqlmodel import Session, col, func, select

from ptcgp_auto_v2.core.task_ordering import build_task_instance_order_by
from ptcgp_auto_v2.db.engine import get_engine
from ptcgp_auto_v2.core.task_status import TaskStatus
from ptcgp_auto_v2.db.models import Account, AccountTaskPlan, TaskInstance


class TaskInstanceRepository:
    """任务实例数据访问层"""

    @staticmethod
    def _build_due_pending_condition(now: datetime):
        """构建 pending 且到期可执行的查询条件。"""
        return (TaskInstance.status == "pending") & (
            (TaskInstance.next_run_at == None)  # noqa: E711
            | (TaskInstance.next_run_at <= now)
        )

    def get_by_id(self, instance_id: int) -> Optional[TaskInstance]:
        """根据 ID 获取任务实例"""
        with Session(get_engine()) as session:
            instance = session.get(TaskInstance, instance_id)
            if instance:
                # 加载关联的账号
                _ = instance.account
            return instance

    def get_by_account_and_type(
        self,
        account_id: int,
        task_type: str,
    ) -> Optional[TaskInstance]:
        """根据账号和任务类型获取任务实例"""
        with Session(get_engine()) as session:
            statement = select(TaskInstance).where(
                TaskInstance.account_id == account_id,
                TaskInstance.task_type == task_type,
            )
            return session.exec(statement).first()

    def get_or_create(
        self,
        account_id: int,
        task_type: str,
        reset_type: str = "daily",
    ) -> TaskInstance:
        """获取或创建任务实例"""
        instance = self.get_by_account_and_type(account_id, task_type)
        if instance:
            return instance

        # 创建新实例
        instance = TaskInstance(
            account_id=account_id,
            task_type=task_type,
            status="pending",
            reset_type=reset_type,
        )
        return self.create(instance)

    def get_next_pending(self) -> Optional[TaskInstance]:
        """获取下一个待执行的任务实例"""
        now = datetime.now()
        with Session(get_engine()) as session:
            statement = (
                select(TaskInstance)
                .where(self._build_due_pending_condition(now))
                .options(
                    selectinload(cast(Any, TaskInstance.account))
                    .selectinload(cast(Any, Account.task_plan_associations))
                    .selectinload(cast(Any, AccountTaskPlan.task_plan))
                )
                .order_by(col(TaskInstance.created_at))
                .limit(1)
            )
            instance = session.exec(statement).first()
            if instance:
                # 加载关联的账号
                _ = instance.account
            return instance

    def get_next_pending_excluding_busy_accounts(self) -> Optional[TaskInstance]:
        """获取下一个待执行的任务实例（排除正在执行任务的账号）

        用于防止同一账号被同时分配到多个设备。
        """
        now = datetime.now()
        with Session(get_engine()) as session:
            # 获取正在执行任务的账号 ID 列表
            busy_accounts_stmt = select(TaskInstance.account_id).where(
                TaskInstance.status == "running"
            )
            busy_account_ids = [row for row in session.exec(busy_accounts_stmt)]

            statement = (
                select(TaskInstance)
                .where(self._build_due_pending_condition(now))
                .where(col(TaskInstance.account_id).notin_(busy_account_ids))
                .options(
                    selectinload(cast(Any, TaskInstance.account))
                    .selectinload(cast(Any, Account.task_plan_associations))
                    .selectinload(cast(Any, AccountTaskPlan.task_plan))
                )
                .order_by(col(TaskInstance.created_at))
                .limit(1)
            )
            instance = session.exec(statement).first()
            if instance:
                # 加载关联的账号
                _ = instance.account
            return instance

    def get_pending_by_account(self, account_id: int) -> List[TaskInstance]:
        """获取账号的所有待执行任务（不排序，由调度器决定顺序）"""
        now = datetime.now()
        with Session(get_engine()) as session:
            statement = (
                select(TaskInstance)
                .where(
                    TaskInstance.account_id == account_id,
                    self._build_due_pending_condition(now),
                )
                .options(
                    selectinload(cast(Any, TaskInstance.account))
                    .selectinload(cast(Any, Account.task_plan_associations))
                    .selectinload(cast(Any, AccountTaskPlan.task_plan))
                )
                # 不排序，由调度器根据 task_plan 的 task_types 顺序重新排序
            )
            return list(session.exec(statement).all())

    def get_blocked_by_account(self, account_id: int) -> List[TaskInstance]:
        """获取账号的所有被阻塞任务"""
        with Session(get_engine()) as session:
            statement = (
                select(TaskInstance)
                .where(
                    TaskInstance.account_id == account_id,
                    TaskInstance.status == "blocked",
                )
                .options(
                    selectinload(cast(Any, TaskInstance.account))
                    .selectinload(cast(Any, Account.task_plan_associations))
                    .selectinload(cast(Any, AccountTaskPlan.task_plan))
                )
                .order_by(col(TaskInstance.created_at))
            )
            return list(session.exec(statement).all())

    def count_by_status(self, status: str) -> int:
        """统计指定状态的任务数量"""
        with Session(get_engine()) as session:
            statement = (
                select(func.count())
                .select_from(TaskInstance)
                .where(TaskInstance.status == status)
            )
            result = session.exec(statement).one()
            return result or 0

    def get_accounts_with_pending_tasks(self) -> List[int]:
        """
        获取所有有待执行任务的账号 ID 列表

        按 pending 任务实例优先级排序后去重：
        1. 先按 reset_type 优先级排序（once 优先）
        2. 同优先级内按 (next_run_at ASC, last_completed_at ASC) 排序
        3. 然后按任务实例顺序提取账号 ID，保持首次出现的顺序去重
        NULL 值视为"最旧"，排在前面
        """
        now = datetime.now()
        with Session(get_engine()) as session:
            # 先查询所有 pending 任务实例并按统一调度优先级排序
            statement = (
                select(TaskInstance)
                .where(self._build_due_pending_condition(now))
                .order_by(*build_task_instance_order_by("dispatch_priority", "asc"))
            )
            instances = session.exec(statement).all()

            # 按首次出现顺序去重
            seen = set()
            ordered_account_ids = []
            for instance in instances:
                if instance.account_id not in seen:
                    seen.add(instance.account_id)
                    ordered_account_ids.append(instance.account_id)

            return ordered_account_ids

    def has_running_tasks(self, account_id: int) -> bool:
        """检查账号是否有正在执行的任务"""
        with Session(get_engine()) as session:
            statement = (
                select(TaskInstance)
                .where(
                    TaskInstance.account_id == account_id,
                    TaskInstance.status == "running",
                )
                .limit(1)
            )
            return session.exec(statement).first() is not None

    def create(self, instance: TaskInstance) -> TaskInstance:
        """创建任务实例"""
        with Session(get_engine()) as session:
            session.add(instance)
            session.commit()
            session.refresh(instance)
            # 加载关联的账号
            _ = instance.account
            return instance

    def update(self, instance: TaskInstance) -> bool:
        """更新任务实例"""
        with Session(get_engine()) as session:
            db_instance = session.get(TaskInstance, instance.id)
            if not db_instance:
                return False
            db_instance.status = instance.status
            db_instance.error_message = instance.error_message
            db_instance.last_completed_at = instance.last_completed_at
            db_instance.schedule_anchor_at = instance.schedule_anchor_at
            db_instance.last_duration_seconds = instance.last_duration_seconds
            db_instance.next_run_at = instance.next_run_at
            db_instance.updated_at = datetime.now()
            session.add(db_instance)
            session.commit()
            return True

    def list_by_account_and_task_types(
        self, account_id: int, task_types: List[str]
    ) -> List[TaskInstance]:
        """按账号与任务类型列表获取任务实例。"""
        if not task_types:
            return []
        with Session(get_engine()) as session:
            statement = select(TaskInstance).where(
                TaskInstance.account_id == account_id,
                col(TaskInstance.task_type).in_(task_types),
            )
            return list(session.exec(statement).all())

    def update_next_run_at(self, instances: List[TaskInstance]) -> int:
        """批量更新任务实例的 next_run_at。"""
        if not instances:
            return 0
        with Session(get_engine()) as session:
            count = 0
            for instance in instances:
                db_instance = session.get(TaskInstance, instance.id)
                if not db_instance:
                    continue
                db_instance.next_run_at = instance.next_run_at
                db_instance.updated_at = datetime.now()
                session.add(db_instance)
                count += 1
            session.commit()
            return count

    def ensure_pending(
        self, account_id: int, task_type: str, reset_type: str
    ) -> TaskInstance:
        """确保指定任务实例存在且处于 pending 状态。"""
        instance = self.get_or_create(
            account_id=account_id,
            task_type=task_type,
            reset_type=reset_type,
        )
        if instance.status != TaskStatus.PENDING.value:
            instance.status = TaskStatus.PENDING.value
            instance.next_run_at = None
            instance.save()
        elif instance.next_run_at is not None:
            instance.next_run_at = None
            instance.save()
        return instance

    def reset_all_pending(self) -> int:
        """将所有异常状态的任务重置为待执行（用于程序重启后恢复）

        重置的状态包括：
        - running: 任务正在执行中被中断
        - blocked: 任务等待前置任务完成，但前置任务没有完成就退出了
        - skipped: 任务被跳过（12小时内已开包等），重启后重新检查
        - failed: 任务执行失败，重启后重试
        """
        with Session(get_engine()) as session:
            statement = select(TaskInstance).where(
                col(TaskInstance.status).in_(
                    ["running", "blocked", "skipped", "failed"]
                )
            )
            instances = session.exec(statement).all()
            count = 0
            for instance in instances:
                instance.status = "pending"
                instance.updated_at = datetime.now()
                session.add(instance)
                count += 1
            session.commit()
            return count

    def reset_stale_tasks(
        self,
        stale_timeout_seconds: int,
        skipped_timeout_seconds: int,
        exclude_account_ids: Optional[List[int]] = None,
    ) -> int:
        """重置超时的异常状态任务（用于 daemon 模式定期清理）

        Args:
            stale_timeout_seconds: running/blocked 状态的超时时间（秒）
            skipped_timeout_seconds: skipped 状态的超时时间（秒）

        Returns:
            重置的任务数量
        """
        with Session(get_engine()) as session:
            now = datetime.now()
            stale_threshold = datetime.fromtimestamp(
                now.timestamp() - stale_timeout_seconds
            )
            skipped_threshold = datetime.fromtimestamp(
                now.timestamp() - skipped_timeout_seconds
            )

            statement = select(TaskInstance).where(
                # running 超时
                (
                    (TaskInstance.status == "running")
                    & (TaskInstance.updated_at < stale_threshold)
                )
                # failed 直接重试
                | (TaskInstance.status == "failed")
                # blocked 超时
                | (
                    (TaskInstance.status == "blocked")
                    & (TaskInstance.updated_at < stale_threshold)
                )
                # skipped 超时后重新检查
                | (
                    (TaskInstance.status == "skipped")
                    & (TaskInstance.updated_at < skipped_threshold)
                )
            )
            if exclude_account_ids:
                statement = statement.where(
                    col(TaskInstance.account_id).notin_(exclude_account_ids)
                )
            instances = session.exec(statement).all()
            count = 0
            for instance in instances:
                instance.status = "pending"
                instance.updated_at = datetime.now()
                session.add(instance)
                count += 1
            session.commit()
            return count

    def delete(self, instance_id: int) -> bool:
        """删除任务实例"""
        with Session(get_engine()) as session:
            instance = session.get(TaskInstance, instance_id)
            if instance:
                session.delete(instance)
                session.commit()
                return True
            return False
