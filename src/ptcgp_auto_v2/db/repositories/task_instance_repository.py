# -*- coding: utf-8 -*-
from collections import defaultdict
from datetime import datetime
from typing import Any, Optional, cast

from sqlalchemy import and_, or_
from sqlalchemy.orm import selectinload
from sqlmodel import col, func, select, update

from ptcgp_auto_v2.core.scheduling_service import (
    build_due_pending_condition,
    build_task_instance_order_by,
)
from ptcgp_auto_v2.core.task_status import TaskStatus
from ptcgp_auto_v2.db.models import Account, AccountTaskPlan, TaskInstance

from .base import BaseRepository

_MISSING = object()


class TaskInstanceRepository(BaseRepository):
    """任务实例数据访问层"""

    @staticmethod
    def _account_options() -> list[Any]:
        """统一账号预加载选项。"""
        return [
            selectinload(cast(Any, TaskInstance.account))
            .selectinload(cast(Any, Account.task_plan_associations))
            .selectinload(cast(Any, AccountTaskPlan.task_plan))
        ]

    def get_by_id(self, instance_id: int) -> Optional[TaskInstance]:
        """根据 ID 获取任务实例"""
        statement = (
            select(TaskInstance)
            .where(TaskInstance.id == instance_id)
            .options(*self._account_options())
        )
        return self.session.exec(statement).first()

    def get_by_account_and_type(
        self,
        account_id: int,
        task_type: str,
    ) -> Optional[TaskInstance]:
        """根据账号和任务类型获取任务实例"""
        statement = select(TaskInstance).where(
            TaskInstance.account_id == account_id,
            TaskInstance.task_type == task_type,
        )
        return self.session.exec(statement).first()

    def get_or_create(
        self,
        account_id: int,
        task_type: str,
        reset_type: str = "daily",
    ) -> TaskInstance:
        """获取或创建任务实例"""
        instance = self.get_by_account_and_type(account_id, task_type)
        if instance is not None:
            return instance
        return self.create(
            TaskInstance(
                account_id=account_id,
                task_type=task_type,
                status="pending",
                reset_type=reset_type,
            )
        )

    def get_pending_by_account_ids(
        self, account_ids: list[int]
    ) -> dict[int, list[TaskInstance]]:
        """批量获取多个账号的待执行任务。"""
        if not account_ids:
            return {}
        now = datetime.now()
        statement = (
            select(TaskInstance)
            .where(
                col(TaskInstance.account_id).in_(account_ids),
                build_due_pending_condition(now),
            )
            .options(*self._account_options())
            .order_by(*build_task_instance_order_by("dispatch_priority", "asc"))
        )
        grouped: dict[int, list[TaskInstance]] = defaultdict(list)
        for instance in self.session.exec(statement).all():
            grouped[instance.account_id].append(instance)
        return dict(grouped)

    def get_blocked_by_account(self, account_id: int) -> list[TaskInstance]:
        """获取账号的所有被阻塞任务"""
        statement = (
            select(TaskInstance)
            .where(
                TaskInstance.account_id == account_id,
                TaskInstance.status == "blocked",
            )
            .options(*self._account_options())
            .order_by(col(TaskInstance.created_at))
        )
        return list(self.session.exec(statement).all())

    def count_by_status(self, status: str) -> int:
        """统计指定状态的任务数量"""
        statement = (
            select(func.count())
            .select_from(TaskInstance)
            .where(TaskInstance.status == status)
        )
        result = self.session.exec(statement).one()
        return result or 0

    def get_accounts_with_pending_tasks(self) -> list[int]:
        """获取所有有待执行任务的账号 ID 列表。"""
        now = datetime.now()
        statement = (
            select(TaskInstance)
            .where(build_due_pending_condition(now))
            .order_by(*build_task_instance_order_by("dispatch_priority", "asc"))
        )
        seen: set[int] = set()
        ordered_account_ids: list[int] = []
        for instance in self.session.exec(statement).all():
            if instance.account_id not in seen:
                seen.add(instance.account_id)
                ordered_account_ids.append(instance.account_id)
        return ordered_account_ids

    def get_running_account_ids(self, account_ids: list[int]) -> set[int]:
        """批量获取当前有 running 任务的账号 ID 集合。"""
        if not account_ids:
            return set()
        statement = select(TaskInstance.account_id).where(
            col(TaskInstance.account_id).in_(account_ids),
            TaskInstance.status == TaskStatus.RUNNING.value,
        )
        return {account_id for account_id in self.session.exec(statement).all()}

    def create(self, instance: TaskInstance) -> TaskInstance:
        """创建任务实例"""
        self.session.add(instance)
        self._finish_write(instance)
        return instance

    def update_runtime_state(
        self,
        instance_id: int,
        *,
        status: str | object = _MISSING,
        reset_type: str | object = _MISSING,
        error_message: str | None | object = _MISSING,
        last_completed_at: datetime | None | object = _MISSING,
        schedule_anchor_at: datetime | None | object = _MISSING,
        last_duration_seconds: int | None | object = _MISSING,
        next_run_at: datetime | None | object = _MISSING,
    ) -> bool:
        """按任务实例 ID 更新运行态字段。"""
        db_instance = self.session.get(TaskInstance, instance_id)
        if not db_instance:
            return False
        now = datetime.now()
        status_changed = False

        if status is not _MISSING:
            if db_instance.status != status:
                status_changed = True
            db_instance.status = status  # type: ignore[assignment]
        if reset_type is not _MISSING:
            db_instance.reset_type = reset_type  # type: ignore[assignment]
        if error_message is not _MISSING:
            db_instance.error_message = error_message  # type: ignore[assignment]
        if last_completed_at is not _MISSING:
            db_instance.last_completed_at = last_completed_at  # type: ignore[assignment]
        if schedule_anchor_at is not _MISSING:
            db_instance.schedule_anchor_at = schedule_anchor_at  # type: ignore[assignment]
        if last_duration_seconds is not _MISSING:
            db_instance.last_duration_seconds = last_duration_seconds  # type: ignore[assignment]
        if next_run_at is not _MISSING:
            db_instance.next_run_at = next_run_at  # type: ignore[assignment]
        if status_changed:
            db_instance.status_changed_at = now
        db_instance.updated_at = now
        self.session.add(db_instance)
        self._finish_write()
        return True

    def set_status_for_ids(self, instance_ids: list[int], status: str) -> int:
        """批量按 ID 更新任务状态。"""
        if not instance_ids:
            return 0
        now = datetime.now()
        values: dict[str, object] = {
            "status": status,
            "status_changed_at": now,
            "updated_at": now,
        }
        if status == TaskStatus.RUNNING.value:
            # 变更原因：任务重新进入 running 后，旧失败原因不再代表当前运行态。
            values["error_message"] = None
        statement = (
            update(TaskInstance)
            .where(col(TaskInstance.id).in_(instance_ids))
            .values(**values)
        )
        result = self.session.exec(statement)
        self._finish_write()
        return result.rowcount or 0

    def list_by_account(self, account_id: int) -> list[TaskInstance]:
        """按账号获取全部任务实例。"""
        statement = select(TaskInstance).where(TaskInstance.account_id == account_id)
        return list(self.session.exec(statement).all())

    def update_scheduling_fields(self, instances: list[TaskInstance]) -> int:
        """批量更新任务实例调度字段。"""
        if not instances:
            return 0

        incoming_by_id = {
            instance.id: instance for instance in instances if instance.id is not None
        }
        if not incoming_by_id:
            return 0

        statement = select(
            TaskInstance.id,
            TaskInstance.reset_type,
            TaskInstance.next_run_at,
        ).where(col(TaskInstance.id).in_(incoming_by_id))
        with self.session.no_autoflush:
            # 变更原因：真实调度路径会传入同 Session 托管对象，autoflush/identity map 会把新旧值抹平。
            db_values_by_id = {
                instance_id: (reset_type, next_run_at)
                for instance_id, reset_type, next_run_at in self.session.exec(
                    statement
                ).all()
            }

        now = datetime.now()
        count = 0
        for instance_id, (db_reset_type, db_next_run_at) in db_values_by_id.items():
            incoming = incoming_by_id[instance_id]
            changed = db_reset_type != incoming.reset_type
            changed = changed or db_next_run_at != incoming.next_run_at
            if not changed:
                continue

            with self.session.no_autoflush:
                db_instance = self.session.get(TaskInstance, instance_id)
            if db_instance is None:
                continue
            db_instance.reset_type = incoming.reset_type
            db_instance.next_run_at = incoming.next_run_at
            db_instance.updated_at = now
            self.session.add(db_instance)
            count += 1

        if count > 0:
            self._finish_write()
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
        if (
            instance.status != TaskStatus.PENDING.value
            or instance.next_run_at is not None
        ):
            if instance.id is None:
                raise RuntimeError("任务实例 ID 为空，无法重置")
            instance.status = TaskStatus.PENDING.value
            instance.next_run_at = None
            self.update_runtime_state(
                instance.id,
                status=TaskStatus.PENDING.value,
                next_run_at=None,
            )
        return instance

    def reset_stale_tasks(
        self,
        stale_timeout_seconds: Optional[int] = None,
        skipped_timeout_seconds: Optional[int] = None,
        exclude_account_ids: Optional[list[int]] = None,
        force_all: bool = False,
    ) -> int:
        """重置异常状态任务（支持超时/冷却或强制重置）"""
        now = datetime.now()
        status_col = col(TaskInstance.status)
        state_changed_col = func.coalesce(
            col(TaskInstance.status_changed_at),
            col(TaskInstance.updated_at),
        )
        if force_all:
            condition = status_col.in_(["running", "blocked", "skipped", "failed"])
        else:
            if stale_timeout_seconds is None or skipped_timeout_seconds is None:
                raise ValueError("未提供超时/冷却时间")
            stale_threshold = datetime.fromtimestamp(
                now.timestamp() - stale_timeout_seconds
            )
            skipped_threshold = datetime.fromtimestamp(
                now.timestamp() - skipped_timeout_seconds
            )
            condition = or_(
                and_(
                    status_col.in_(["running", "blocked"]),
                    state_changed_col < stale_threshold,
                ),
                and_(
                    status_col.in_(["skipped", "failed"]),
                    state_changed_col < skipped_threshold,
                ),
            )

        if exclude_account_ids:
            condition = and_(
                condition, col(TaskInstance.account_id).notin_(exclude_account_ids)
            )

        statement = (
            update(TaskInstance)
            .where(condition)
            .values(status="pending", status_changed_at=now, updated_at=now)
        )
        result = self.session.exec(statement)
        self._finish_write()
        return result.rowcount or 0

    def delete(self, instance_id: int) -> bool:
        """删除任务实例"""
        instance = self.session.get(TaskInstance, instance_id)
        if instance is None:
            return False
        self.session.delete(instance)
        self._finish_write()
        return True
