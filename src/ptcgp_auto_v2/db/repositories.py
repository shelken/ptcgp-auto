# -*- coding: utf-8 -*-
"""
数据访问层（Repository）

封装数据库 CRUD 操作，提供业务逻辑接口。
"""

import logging
from datetime import datetime, date
from typing import List, Optional

from ptcgp_auto_v2.db.connection import get_database
from ptcgp_auto_v2.db.models import (
    Account,
    TaskPlan,
    TaskInstance,
    PackRecord,
    AccountPackConfig,
)

logger = logging.getLogger(__name__)


class TaskPlanRepository:
    """任务计划数据访问层"""

    def __init__(self):
        self.db = get_database()

    def get_by_id(self, plan_id: int) -> Optional[TaskPlan]:
        """根据 ID 获取任务计划"""
        cursor = self.db.execute("SELECT * FROM task_plans WHERE id = ?", (plan_id,))
        row = cursor.fetchone()
        return TaskPlan.from_row(row)

    def get_by_name(self, name: str) -> Optional[TaskPlan]:
        """根据名称获取任务计划"""
        cursor = self.db.execute("SELECT * FROM task_plans WHERE name = ?", (name,))
        row = cursor.fetchone()
        return TaskPlan.from_row(row)

    def get_all(self) -> List[TaskPlan]:
        """获取所有任务计划"""
        cursor = self.db.execute("SELECT * FROM task_plans ORDER BY id")
        return [TaskPlan.from_row(row) for row in cursor.fetchall()]

    def create(self, plan: TaskPlan) -> TaskPlan:
        """创建任务计划"""
        cursor = self.db.execute(
            """
            INSERT INTO task_plans (name, description, task_types)
            VALUES (?, ?, ?)
            """,
            (plan.name, plan.description, plan.task_types_json()),
        )
        self.db.commit()
        plan.id = cursor.lastrowid
        return plan

    def update(self, plan: TaskPlan) -> bool:
        """更新任务计划"""
        self.db.execute(
            """
            UPDATE task_plans
            SET name = ?, description = ?, task_types = ?
            WHERE id = ?
            """,
            (plan.name, plan.description, plan.task_types_json(), plan.id),
        )
        self.db.commit()
        return True

    def delete(self, plan_id: int) -> bool:
        """删除任务计划"""
        self.db.execute("DELETE FROM task_plans WHERE id = ?", (plan_id,))
        self.db.commit()
        return True


class AccountRepository:
    """账号数据访问层"""

    def __init__(self):
        self.db = get_database()

    def get_by_id(self, account_id: int) -> Optional[Account]:
        """根据 ID 获取账号"""
        cursor = self.db.execute("SELECT * FROM accounts WHERE id = ?", (account_id,))
        row = cursor.fetchone()
        account = Account.from_row(row)

        # 加载关联的任务计划
        if account and account.task_plan_id:
            plan_repo = TaskPlanRepository()
            account.task_plan = plan_repo.get_by_id(account.task_plan_id)

        return account

    def get_by_game_id(self, game_id: str) -> Optional[Account]:
        """根据游戏 ID（deviceAccount）获取账号"""
        cursor = self.db.execute("SELECT * FROM accounts WHERE game_id = ?", (game_id,))
        row = cursor.fetchone()
        return Account.from_row(row)

    def get_by_friend_id(self, friend_id: str) -> Optional[Account]:
        """根据朋友 ID 获取账号"""
        cursor = self.db.execute(
            "SELECT * FROM accounts WHERE friend_id = ?", (friend_id,)
        )
        row = cursor.fetchone()
        return Account.from_row(row)

    def get_all(self) -> List[Account]:
        """获取所有账号"""
        cursor = self.db.execute("SELECT * FROM accounts ORDER BY id")
        return [Account.from_row(row) for row in cursor.fetchall()]

    def get_accounts_without_friend_id(self) -> List[Account]:
        """获取所有没有 friend_id 的账号（用于补全任务）"""
        cursor = self.db.execute(
            "SELECT * FROM accounts WHERE friend_id IS NULL OR friend_id = '' ORDER BY id"
        )
        return [Account.from_row(row) for row in cursor.fetchall()]

    def get_accounts_with_plans(self) -> List[Account]:
        """获取所有有任务计划的账号"""
        cursor = self.db.execute(
            """
            SELECT a.*, p.id as plan_id, p.name as plan_name,
                   p.description as plan_description, p.task_types as plan_task_types
            FROM accounts a
            JOIN task_plans p ON a.task_plan_id = p.id
            ORDER BY a.id
            """
        )

        accounts = []
        for row in cursor.fetchall():
            account = Account.from_row(row)
            if account:
                # 构建关联的任务计划
                import json

                task_types = row["plan_task_types"]
                if isinstance(task_types, str):
                    try:
                        task_types = json.loads(task_types)
                    except (json.JSONDecodeError, TypeError):
                        task_types = []

                account.task_plan = TaskPlan(
                    id=row["plan_id"],
                    name=row["plan_name"],
                    description=row["plan_description"],
                    task_types=task_types or [],
                )
                accounts.append(account)

        return accounts

    def create(self, account: Account) -> Account:
        """创建账号"""
        cursor = self.db.execute(
            """
            INSERT INTO accounts (game_id, friend_id, nintendo_id, nickname, level, country,
                                  xml_content, session_token_iat, task_plan_id)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                account.game_id,
                account.friend_id,
                account.nintendo_id,
                account.nickname,
                account.level,
                account.country,
                account.xml_content,
                account.session_token_iat,
                account.task_plan_id,
            ),
        )
        self.db.commit()
        account.id = cursor.lastrowid
        return account

    def update(self, account: Account) -> bool:
        """更新账号"""
        self.db.execute(
            """
            UPDATE accounts
            SET game_id = ?, friend_id = ?, nintendo_id = ?, nickname = ?, level = ?, country = ?,
                xml_content = ?, session_token_iat = ?, task_plan_id = ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (
                account.game_id,
                account.friend_id,
                account.nintendo_id,
                account.nickname,
                account.level,
                account.country,
                account.xml_content,
                account.session_token_iat,
                account.task_plan_id,
                account.id,
            ),
        )
        self.db.commit()
        return True

    def update_friend_id(self, account_id: int, friend_id: str) -> bool:
        """更新账号的 friend_id"""
        self.db.execute(
            """
            UPDATE accounts
            SET friend_id = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (friend_id, account_id),
        )
        self.db.commit()
        return True

    def delete(self, account_id: int) -> bool:
        """删除账号"""
        self.db.execute("DELETE FROM accounts WHERE id = ?", (account_id,))
        self.db.commit()
        return True

    def assign_task_plan(self, account_id: int, plan_id: int) -> bool:
        """为账号分配任务计划"""
        self.db.execute(
            """
            UPDATE accounts
            SET task_plan_id = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (plan_id, account_id),
        )
        self.db.commit()
        return True


class TaskInstanceRepository:
    """任务实例数据访问层"""

    def __init__(self):
        self.db = get_database()

    def get_by_id(self, instance_id: int) -> Optional[TaskInstance]:
        """根据 ID 获取任务实例"""
        cursor = self.db.execute(
            "SELECT * FROM task_instances WHERE id = ?", (instance_id,)
        )
        row = cursor.fetchone()
        instance = TaskInstance.from_row(row)

        # 加载关联的账号
        if instance:
            account_repo = AccountRepository()
            instance.account = account_repo.get_by_id(instance.account_id)

        return instance

    def get_by_account_and_type(
        self,
        account_id: int,
        task_type: str,
    ) -> Optional[TaskInstance]:
        """根据账号和任务类型获取任务实例"""
        cursor = self.db.execute(
            """
            SELECT * FROM task_instances
            WHERE account_id = ? AND task_type = ?
            """,
            (account_id, task_type),
        )
        row = cursor.fetchone()
        return TaskInstance.from_row(row)

    def get_or_create(
        self,
        account_id: int,
        task_type: str,
        reset_type: str = "daily",
    ) -> TaskInstance:
        """获取或创建任务实例"""
        instance = self.get_by_account_and_type(account_id, task_type)
        if instance:
            # 加载关联的账号
            account_repo = AccountRepository()
            instance.account = account_repo.get_by_id(account_id)
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
        cursor = self.db.execute(
            """
            SELECT ti.*
            FROM task_instances ti
            WHERE ti.status = 'pending'
            ORDER BY ti.created_at ASC
            LIMIT 1
            """
        )
        row = cursor.fetchone()
        if not row:
            return None

        instance = TaskInstance.from_row(row)
        if instance:
            # 使用 AccountRepository 加载完整的账号信息
            account_repo = AccountRepository()
            instance.account = account_repo.get_by_id(instance.account_id)

        return instance

    def get_next_pending_excluding_busy_accounts(self) -> Optional[TaskInstance]:
        """获取下一个待执行的任务实例（排除正在执行任务的账号）

        用于防止同一账号被同时分配到多个设备。
        """
        cursor = self.db.execute(
            """
            SELECT ti.*
            FROM task_instances ti
            WHERE ti.status = 'pending'
              AND ti.account_id NOT IN (
                  SELECT DISTINCT account_id
                  FROM task_instances
                  WHERE status = 'running'
              )
            ORDER BY ti.created_at ASC
            LIMIT 1
            """
        )
        row = cursor.fetchone()
        if not row:
            return None

        instance = TaskInstance.from_row(row)
        if instance:
            account_repo = AccountRepository()
            instance.account = account_repo.get_by_id(instance.account_id)

        return instance

    def get_pending_by_account(self, account_id: int) -> List[TaskInstance]:
        """获取账号的所有待执行任务"""
        cursor = self.db.execute(
            """
            SELECT * FROM task_instances
            WHERE account_id = ? AND status = 'pending'
            ORDER BY created_at ASC
            """,
            (account_id,),
        )
        return [TaskInstance.from_row(row) for row in cursor.fetchall()]

    def get_blocked_by_account(self, account_id: int) -> List[TaskInstance]:
        """获取账号的所有被阻塞任务"""
        cursor = self.db.execute(
            """
            SELECT * FROM task_instances
            WHERE account_id = ? AND status = 'blocked'
            ORDER BY created_at ASC
            """,
            (account_id,),
        )
        return [TaskInstance.from_row(row) for row in cursor.fetchall()]

    def count_by_status(self, status: str) -> int:
        """统计指定状态的任务数量"""
        cursor = self.db.execute(
            "SELECT COUNT(*) as cnt FROM task_instances WHERE status = ?", (status,)
        )
        row = cursor.fetchone()
        return row["cnt"] if row else 0

    def create(self, instance: TaskInstance) -> TaskInstance:
        """创建任务实例"""
        cursor = self.db.execute(
            """
            INSERT INTO task_instances
            (account_id, task_type, status, reset_type, error_message)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                instance.account_id,
                instance.task_type,
                instance.status,
                instance.reset_type,
                instance.error_message,
            ),
        )
        self.db.commit()
        instance.id = cursor.lastrowid

        # 加载关联的账号
        account_repo = AccountRepository()
        instance.account = account_repo.get_by_id(instance.account_id)

        return instance

    def update(self, instance: TaskInstance) -> bool:
        """更新任务实例"""
        self.db.execute(
            """
            UPDATE task_instances
            SET status = ?, error_message = ?, last_completed_at = ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (
                instance.status,
                instance.error_message,
                instance.last_completed_at,
                instance.id,
            ),
        )
        self.db.commit()
        return True

    def reset_all_pending(self) -> int:
        """将所有异常状态的任务重置为待执行（用于程序重启后恢复）

        重置的状态包括：
        - running: 任务正在执行中被中断
        - blocked: 任务等待前置任务完成，但前置任务没有完成就退出了
        """
        cursor = self.db.execute(
            """
            UPDATE task_instances
            SET status = 'pending', updated_at = CURRENT_TIMESTAMP
            WHERE status IN ('running', 'blocked')
            """
        )
        self.db.commit()
        return cursor.rowcount

    def delete(self, instance_id: int) -> bool:
        """删除任务实例"""
        self.db.execute("DELETE FROM task_instances WHERE id = ?", (instance_id,))
        self.db.commit()
        return True


class AccountPackConfigRepository:
    """账号开包配置数据访问层"""

    def __init__(self):
        self.db = get_database()

    def get_by_account_and_type(
        self, account_id: int, config_type: str
    ) -> Optional[AccountPackConfig]:
        """根据账号和类型获取开包配置"""
        cursor = self.db.execute(
            """
            SELECT * FROM account_pack_config
            WHERE account_id = ? AND type = ?
            """,
            (account_id, config_type),
        )
        row = cursor.fetchone()
        return AccountPackConfig.from_row(row)

    def get_by_account(self, account_id: int) -> List[AccountPackConfig]:
        """获取账号的所有开包配置"""
        cursor = self.db.execute(
            """
            SELECT * FROM account_pack_config
            WHERE account_id = ?
            ORDER BY type
            """,
            (account_id,),
        )
        configs = []
        for row in cursor.fetchall():
            config = AccountPackConfig.from_row(row)
            if config:
                configs.append(config)
        return configs

    def create(self, config: AccountPackConfig) -> AccountPackConfig:
        """创建开包配置"""
        cursor = self.db.execute(
            """
            INSERT INTO account_pack_config (account_id, type, pack_code, booster_name)
            VALUES (?, ?, ?, ?)
            """,
            (config.account_id, config.type, config.pack_code, config.booster_name),
        )
        self.db.commit()
        config.id = cursor.lastrowid
        return config

    def update(self, config: AccountPackConfig) -> bool:
        """更新开包配置"""
        self.db.execute(
            """
            UPDATE account_pack_config
            SET type = ?, pack_code = ?, booster_name = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (config.type, config.pack_code, config.booster_name, config.id),
        )
        self.db.commit()
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
        self.db.execute("DELETE FROM account_pack_config WHERE id = ?", (config_id,))
        self.db.commit()
        return True


class PackRecordRepository:
    """开包记录数据访问层"""

    def __init__(self):
        self.db = get_database()

    def get_by_account(self, account_id: int) -> List[PackRecord]:
        """获取账号的所有开包记录"""
        cursor = self.db.execute(
            """
            SELECT * FROM pack_records
            WHERE account_id = ?
            ORDER BY opened_at DESC
            """,
            (account_id,),
        )
        return [PackRecord.from_row(row) for row in cursor.fetchall()]

    def get_today(self, account_id: int) -> Optional[PackRecord]:
        """获取账号今日的开包记录"""
        cursor = self.db.execute(
            """
            SELECT * FROM pack_records
            WHERE account_id = ? AND date(opened_at, 'localtime') = date('now', 'localtime')
            ORDER BY opened_at DESC
            LIMIT 1
            """,
            (account_id,),
        )
        row = cursor.fetchone()
        return PackRecord.from_row(row)

    def has_opened_today(self, account_id: int) -> bool:
        """检查账号今日是否已开包"""
        return self.get_today(account_id) is not None

    def create(self, record: PackRecord) -> PackRecord:
        """创建开包记录"""
        cursor = self.db.execute(
            """
            INSERT INTO pack_records (account_id, pack_type)
            VALUES (?, ?)
            """,
            (record.account_id, record.pack_type),
        )
        self.db.commit()
        record.id = cursor.lastrowid
        return record

    def create_for_account(self, account_id: int, pack_type: str = "") -> PackRecord:
        """为账号创建开包记录"""
        record = PackRecord(account_id=account_id, pack_type=pack_type)
        return self.create(record)

    def count_by_account(self, account_id: int) -> int:
        """统计账号的开包总数"""
        cursor = self.db.execute(
            "SELECT COUNT(*) as cnt FROM pack_records WHERE account_id = ?",
            (account_id,),
        )
        row = cursor.fetchone()
        return row["cnt"] if row else 0

    def delete(self, record_id: int) -> bool:
        """删除开包记录"""
        self.db.execute("DELETE FROM pack_records WHERE id = ?", (record_id,))
        self.db.commit()
        return True
