# -*- coding: utf-8 -*-
"""
数据访问层（Repository）

使用 SQLModel 封装数据库 CRUD 操作，提供业务逻辑接口。
"""

import json
import logging
from datetime import datetime
from typing import List, Optional

from sqlmodel import Session, col, func, select

from ptcgp_auto_v2.db.engine import get_engine
from ptcgp_auto_v2.db.models import (
    Account,
    AccountPackConfig,
    PackRecord,
    TaskInstance,
    TaskPlan,
)

logger = logging.getLogger(__name__)


class TaskPlanRepository:
    """任务计划数据访问层"""

    def get_by_id(self, plan_id: int) -> Optional[TaskPlan]:
        """根据 ID 获取任务计划"""
        with Session(get_engine()) as session:
            return session.get(TaskPlan, plan_id)

    def get_by_name(self, name: str) -> Optional[TaskPlan]:
        """根据名称获取任务计划"""
        with Session(get_engine()) as session:
            statement = select(TaskPlan).where(TaskPlan.name == name)
            return session.exec(statement).first()

    def get_all(self) -> List[TaskPlan]:
        """获取所有任务计划"""
        with Session(get_engine()) as session:
            statement = select(TaskPlan).order_by(TaskPlan.id)
            return list(session.exec(statement).all())

    def create(self, plan: TaskPlan) -> TaskPlan:
        """创建任务计划"""
        with Session(get_engine()) as session:
            # 如果 task_types 是列表，转换为 JSON 字符串
            if isinstance(plan.task_types, list):
                plan.task_types = json.dumps(plan.task_types, ensure_ascii=False)
            session.add(plan)
            session.commit()
            session.refresh(plan)
            return plan

    def update(self, plan: TaskPlan) -> bool:
        """更新任务计划"""
        with Session(get_engine()) as session:
            db_plan = session.get(TaskPlan, plan.id)
            if not db_plan:
                return False
            db_plan.name = plan.name
            db_plan.description = plan.description
            # 如果 task_types 是列表，转换为 JSON 字符串
            if isinstance(plan.task_types, list):
                db_plan.task_types = json.dumps(plan.task_types, ensure_ascii=False)
            else:
                db_plan.task_types = plan.task_types
            session.add(db_plan)
            session.commit()
            return True

    def delete(self, plan_id: int) -> bool:
        """删除任务计划"""
        with Session(get_engine()) as session:
            plan = session.get(TaskPlan, plan_id)
            if plan:
                session.delete(plan)
                session.commit()
                return True
            return False


class AccountRepository:
    """账号数据访问层"""

    def get_by_id(self, account_id: int) -> Optional[Account]:
        """根据 ID 获取账号"""
        with Session(get_engine()) as session:
            account = session.get(Account, account_id)
            if account and account.task_plan_id:
                # 加载关联的任务计划
                _ = account.task_plan  # 触发加载
            return account

    def get_by_game_id(self, game_id: str) -> Optional[Account]:
        """根据游戏 ID（deviceAccount）获取账号"""
        with Session(get_engine()) as session:
            statement = select(Account).where(Account.game_id == game_id)
            return session.exec(statement).first()

    def get_by_friend_id(self, friend_id: str) -> Optional[Account]:
        """根据朋友 ID 获取账号"""
        with Session(get_engine()) as session:
            statement = select(Account).where(Account.friend_id == friend_id)
            return session.exec(statement).first()

    def get_all(self) -> List[Account]:
        """获取所有账号"""
        with Session(get_engine()) as session:
            statement = select(Account).order_by(Account.id)
            return list(session.exec(statement).all())

    def get_accounts_without_friend_id(self) -> List[Account]:
        """获取所有没有 friend_id 的账号（用于补全任务）"""
        with Session(get_engine()) as session:
            statement = (
                select(Account)
                .where((Account.friend_id.is_(None)) | (Account.friend_id == ""))
                .order_by(Account.id)
            )
            return list(session.exec(statement).all())

    def get_accounts_with_plans(self) -> List[Account]:
        """获取所有有任务计划的账号"""
        with Session(get_engine()) as session:
            statement = (
                select(Account)
                .where(Account.task_plan_id.isnot(None))
                .order_by(Account.id)
            )
            accounts = list(session.exec(statement).all())
            # 预加载任务计划
            for account in accounts:
                if account.task_plan_id:
                    _ = account.task_plan
            return accounts

    def create(self, account: Account) -> Account:
        """创建账号"""
        with Session(get_engine()) as session:
            # 如果没有指定 task_plan，自动关联 "daily"
            if account.task_plan_id is None:
                daily_plan = self.get_plan_by_name(session, "daily")
                if daily_plan:
                    account.task_plan_id = daily_plan.id

            session.add(account)
            session.commit()
            session.refresh(account)
            return account

    def get_plan_by_name(self, session: Session, name: str) -> Optional[TaskPlan]:
        """在现有 session 中根据名称获取任务计划"""
        statement = select(TaskPlan).where(TaskPlan.name == name)
        return session.exec(statement).first()

    def update(self, account: Account) -> bool:
        """更新账号"""
        with Session(get_engine()) as session:
            db_account = session.get(Account, account.id)
            if not db_account:
                return False
            db_account.game_id = account.game_id
            db_account.friend_id = account.friend_id
            db_account.nintendo_id = account.nintendo_id
            db_account.nickname = account.nickname
            db_account.level = account.level
            db_account.country = account.country
            db_account.xml_content = account.xml_content
            db_account.session_token_iat = account.session_token_iat
            db_account.task_plan_id = account.task_plan_id
            db_account.remark = account.remark
            db_account.updated_at = datetime.now()
            session.add(db_account)
            session.commit()
            return True

    def update_friend_id(self, account_id: int, friend_id: str) -> bool:
        """更新账号的 friend_id"""
        with Session(get_engine()) as session:
            account = session.get(Account, account_id)
            if not account:
                return False
            account.friend_id = friend_id
            account.updated_at = datetime.now()
            session.add(account)
            session.commit()
            return True

    def delete(self, account_id: int) -> bool:
        """删除账号"""
        with Session(get_engine()) as session:
            account = session.get(Account, account_id)
            if account:
                session.delete(account)
                session.commit()
                return True
            return False

    def assign_task_plan(self, account_id: int, plan_id: int) -> bool:
        """为账号分配任务计划"""
        with Session(get_engine()) as session:
            account = session.get(Account, account_id)
            if not account:
                return False
            account.task_plan_id = plan_id
            account.updated_at = datetime.now()
            session.add(account)
            session.commit()
            return True


class TaskInstanceRepository:
    """任务实例数据访问层"""

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
        with Session(get_engine()) as session:
            statement = (
                select(TaskInstance)
                .where(TaskInstance.status == "pending")
                .order_by(TaskInstance.created_at)
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
        with Session(get_engine()) as session:
            # 获取正在执行任务的账号 ID 列表
            busy_accounts_stmt = select(TaskInstance.account_id).where(
                TaskInstance.status == "running"
            )
            busy_account_ids = [row for row in session.exec(busy_accounts_stmt)]

            statement = (
                select(TaskInstance)
                .where(TaskInstance.status == "pending")
                .where(col(TaskInstance.account_id).notin_(busy_account_ids))
                .order_by(TaskInstance.created_at)
                .limit(1)
            )
            instance = session.exec(statement).first()
            if instance:
                # 加载关联的账号
                _ = instance.account
            return instance

    def get_pending_by_account(self, account_id: int) -> List[TaskInstance]:
        """获取账号的所有待执行任务"""
        with Session(get_engine()) as session:
            statement = (
                select(TaskInstance)
                .where(
                    TaskInstance.account_id == account_id,
                    TaskInstance.status == "pending",
                )
                .order_by(TaskInstance.created_at)
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
                .order_by(TaskInstance.created_at)
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
        """获取所有有待执行任务的账号 ID 列表"""
        with Session(get_engine()) as session:
            statement = (
                select(TaskInstance.account_id)
                .where(TaskInstance.status == "pending")
                .distinct()
                .order_by(TaskInstance.account_id)
            )
            return list(session.exec(statement).all())

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
            db_instance.updated_at = datetime.now()
            session.add(db_instance)
            session.commit()
            return True

    def reset_all_pending(self) -> int:
        """将所有异常状态的任务重置为待执行（用于程序重启后恢复）

        重置的状态包括：
        - running: 任务正在执行中被中断
        - blocked: 任务等待前置任务完成，但前置任务没有完成就退出了
        - skipped: 任务被跳过（12小时内已开包等），重启后重新检查
        - failed: 任务执行失败，重启后重试
        """
        with Session(get_engine()) as session:
            statement = (
                select(TaskInstance)
                .where(
                    col(TaskInstance.status).in_(
                        ["running", "blocked", "skipped", "failed"]
                    )
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
        self, stale_timeout_seconds: int, skipped_timeout_seconds: int
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
                ((TaskInstance.status == "running") & (TaskInstance.updated_at < stale_threshold))
                # failed 直接重试
                | (TaskInstance.status == "failed")
                # blocked 超时
                | ((TaskInstance.status == "blocked") & (TaskInstance.updated_at < stale_threshold))
                # skipped 超时后重新检查
                | ((TaskInstance.status == "skipped") & (TaskInstance.updated_at < skipped_threshold))
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


class AccountPackConfigRepository:
    """账号开包配置数据访问层"""

    def get_by_account_and_type(
        self, account_id: int, config_type: str
    ) -> Optional[AccountPackConfig]:
        """根据账号和类型获取开包配置"""
        with Session(get_engine()) as session:
            statement = select(AccountPackConfig).where(
                AccountPackConfig.account_id == account_id,
                AccountPackConfig.type == config_type,
            )
            return session.exec(statement).first()

    def get_by_account(self, account_id: int) -> List[AccountPackConfig]:
        """获取账号的所有开包配置"""
        with Session(get_engine()) as session:
            statement = (
                select(AccountPackConfig)
                .where(AccountPackConfig.account_id == account_id)
                .order_by(AccountPackConfig.type)
            )
            return list(session.exec(statement).all())

    def create(self, config: AccountPackConfig) -> AccountPackConfig:
        """创建开包配置"""
        with Session(get_engine()) as session:
            session.add(config)
            session.commit()
            session.refresh(config)
            return config

    def update(self, config: AccountPackConfig) -> bool:
        """更新开包配置"""
        with Session(get_engine()) as session:
            db_config = session.get(AccountPackConfig, config.id)
            if not db_config:
                return False
            db_config.type = config.type
            db_config.pack_code = config.pack_code
            db_config.booster_name = config.booster_name
            db_config.updated_at = datetime.now()
            session.add(db_config)
            session.commit()
            return True

    def upsert(self, config: AccountPackConfig) -> AccountPackConfig:
        """创建或更新开包配置"""
        existing = self.get_by_account_and_type(config.account_id, config.type)
        if existing:
            config.id = existing.id
            self.update(config)
            return config
        return self.create(config)

    def delete(self, config_id: int) -> bool:
        """删除开包配置"""
        with Session(get_engine()) as session:
            config = session.get(AccountPackConfig, config_id)
            if config:
                session.delete(config)
                session.commit()
                return True
            return False


class PackRecordRepository:
    """开包记录数据访问层"""

    def get_by_account(self, account_id: int) -> List[PackRecord]:
        """获取账号的所有开包记录"""
        with Session(get_engine()) as session:
            statement = (
                select(PackRecord)
                .where(PackRecord.account_id == account_id)
                .order_by(PackRecord.opened_at.desc())
            )
            return list(session.exec(statement).all())

    def get_today(self, account_id: int) -> Optional[PackRecord]:
        """获取账号今日的开包记录"""
        with Session(get_engine()) as session:
            today = datetime.now().date()
            statement = (
                select(PackRecord)
                .where(
                    PackRecord.account_id == account_id,
                    func.date(PackRecord.opened_at) == today,
                )
                .order_by(PackRecord.opened_at.desc())
                .limit(1)
            )
            return session.exec(statement).first()

    def has_opened_today(self, account_id: int) -> bool:
        """检查账号今日是否已开包"""
        return self.get_today(account_id) is not None

    def has_opened_within_hours(self, account_id: int, hours: int = 12) -> bool:
        """检查账号在指定小时内是否已开包"""
        with Session(get_engine()) as session:
            threshold = datetime.fromtimestamp(
                datetime.now().timestamp() - hours * 3600
            )
            statement = (
                select(PackRecord)
                .where(
                    PackRecord.account_id == account_id,
                    PackRecord.opened_at >= threshold,
                )
                .limit(1)
            )
            return session.exec(statement).first() is not None

    def create(self, record: PackRecord) -> PackRecord:
        """创建开包记录"""
        with Session(get_engine()) as session:
            session.add(record)
            session.commit()
            session.refresh(record)
            return record

    def create_for_account(self, account_id: int, pack_type: str = "") -> PackRecord:
        """为账号创建开包记录"""
        record = PackRecord(account_id=account_id, pack_type=pack_type)
        return self.create(record)

    def count_by_account(self, account_id: int) -> int:
        """统计账号的开包总数"""
        with Session(get_engine()) as session:
            statement = (
                select(func.count())
                .select_from(PackRecord)
                .where(PackRecord.account_id == account_id)
            )
            result = session.exec(statement).one()
            return result or 0

    def delete(self, record_id: int) -> bool:
        """删除开包记录"""
        with Session(get_engine()) as session:
            record = session.get(PackRecord, record_id)
            if record:
                session.delete(record)
                session.commit()
                return True
            return False
