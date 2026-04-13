# -*- coding: utf-8 -*-
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Optional, cast

from sqlalchemy.orm import selectinload
from sqlmodel import col, func, select

from ptcgp_auto_v2.db.models import Account, AccountTaskPlan, TaskPlan

from .base import BaseRepository


@dataclass(slots=True, frozen=True)
class AccountFriendRef:
    """好友关系任务使用的账号最小纯数据。"""

    id: int
    friend_id: Optional[str]


class AccountRepository(BaseRepository):
    """账号数据访问层"""

    @staticmethod
    def _account_options() -> list[Any]:
        """统一账号预加载选项。"""
        return [
            selectinload(cast(Any, Account.task_plan_associations)).selectinload(
                cast(Any, AccountTaskPlan.task_plan)
            ),
            selectinload(cast(Any, Account.account_stat)),
            selectinload(cast(Any, Account.pack_points)),
        ]

    def get_by_id(self, account_id: int) -> Optional[Account]:
        """根据 ID 获取账号"""
        statement = (
            select(Account)
            .where(Account.id == account_id)
            .options(*self._account_options())
        )
        return self.session.exec(statement).first()

    def get_by_ids(self, account_ids: list[int]) -> dict[int, Account]:
        """批量获取账号，并按账号 ID 返回映射。"""
        if not account_ids:
            return {}
        statement = (
            select(Account)
            .where(col(Account.id).in_(account_ids))
            .options(*self._account_options())
        )
        accounts = self.session.exec(statement).all()
        return {account.id: account for account in accounts if account.id is not None}

    def get_by_game_id(self, game_id: str) -> Optional[Account]:
        """根据游戏 ID（deviceAccount）获取账号"""
        statement = select(Account).where(Account.game_id == game_id)
        return self.session.exec(statement).first()

    def get_friend_ref_by_id(self, account_id: int) -> Optional[AccountFriendRef]:
        """根据账号 ID 获取好友关系所需的最小纯数据。"""
        statement = select(Account.id, Account.friend_id).where(Account.id == account_id)
        row = self.session.exec(statement).first()
        if row is None:
            return None
        row_id, friend_id = row
        if row_id is None:
            raise RuntimeError("账号 ID 为空，无法构造好友关系数据")
        return AccountFriendRef(id=int(row_id), friend_id=friend_id)

    def get_all(self) -> list[Account]:
        """获取所有账号"""
        statement = select(Account).options(*self._account_options()).order_by(col(Account.id))
        return list(self.session.exec(statement).all())

    def count_all(self) -> int:
        """统计所有账号数量"""
        statement = select(func.count()).select_from(Account)
        result = self.session.exec(statement).one()
        return result or 0

    def list_accounts_by_plan_id(self, plan_id: int) -> list[Account]:
        """获取关联指定计划的账号列表。"""
        statement = (
            select(Account)
            .join(AccountTaskPlan, col(AccountTaskPlan.account_id) == col(Account.id))
            .where(AccountTaskPlan.task_plan_id == plan_id)
            .options(*self._account_options())
            .order_by(col(Account.id))
        )
        return list(self.session.exec(statement).all())

    def create(self, account: Account, auto_assign_plan: bool = True) -> Account:
        """创建账号。"""
        self.session.add(account)
        self._finish_write(account)

        if auto_assign_plan and not account.task_plan_associations:
            base_plan = self.get_plan_by_name("base")
            if base_plan and account.id is not None and base_plan.id is not None:
                self.session.add(
                    AccountTaskPlan(
                        account_id=account.id,
                        task_plan_id=base_plan.id,
                        priority=0,
                        is_active=True,
                    )
                )
                self._finish_write(account)

        return account

    def update_sync_data(
        self,
        account_id: int,
        *,
        nintendo_id: Optional[str] = None,
        country: Optional[str] = None,
        xml_content: Optional[bytes] = None,
        session_token_iat: Optional[int] = None,
    ) -> bool:
        """按账号 ID 更新同步字段。"""
        db_account = self.session.get(Account, account_id)
        if not db_account:
            return False

        if nintendo_id is not None:
            db_account.nintendo_id = nintendo_id
        if country is not None:
            db_account.country = country
        if xml_content is not None:
            db_account.xml_content = xml_content
        if session_token_iat is not None:
            db_account.session_token_iat = session_token_iat
        db_account.updated_at = datetime.now()
        self.session.add(db_account)
        self._finish_write()
        return True

    def get_plan_by_name(self, name: str) -> Optional[TaskPlan]:
        """根据名称获取任务计划。"""
        statement = select(TaskPlan).where(TaskPlan.name == name)
        return self.session.exec(statement).first()

    def update(self, account: Account) -> bool:
        """更新账号"""
        db_account = self.session.get(Account, account.id)
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
        db_account.remark = account.remark
        db_account.updated_at = datetime.now()
        self.session.add(db_account)
        self._finish_write()
        return True

    def delete(self, account_id: int) -> bool:
        """删除账号"""
        account = self.session.get(Account, account_id)
        if account is None:
            return False
        self.session.delete(account)
        self._finish_write()
        return True

    def add_secondary_plan(
        self, account_id: int, plan_id: int, priority: int = 0
    ) -> bool:
        """为账号添加额外的任务计划。"""
        statement = select(AccountTaskPlan).where(
            AccountTaskPlan.account_id == account_id,
            AccountTaskPlan.task_plan_id == plan_id,
        )
        existing = self.session.exec(statement).first()
        if existing:
            existing.is_active = True
            existing.priority = priority
            existing.updated_at = datetime.now()
            self.session.add(existing)
        else:
            self.session.add(
                AccountTaskPlan(
                    account_id=account_id,
                    task_plan_id=plan_id,
                    priority=priority,
                )
            )
        self._finish_write()
        return True

    def remove_secondary_plan(self, account_id: int, plan_id: int) -> bool:
        """移除账号的额外计划"""
        statement = select(AccountTaskPlan).where(
            AccountTaskPlan.account_id == account_id,
            AccountTaskPlan.task_plan_id == plan_id,
        )
        existing = self.session.exec(statement).first()
        if existing is None:
            return False
        self.session.delete(existing)
        self._finish_write()
        return True

    def update_plan_associations(self, account_id: int, plans_data: list[dict]) -> bool:
        """批量更新账号的任务计划关联。"""
        statement = select(AccountTaskPlan).where(AccountTaskPlan.account_id == account_id)
        existing_assocs = self.session.exec(statement).all()
        existing_map = {assoc.task_plan_id: assoc for assoc in existing_assocs}
        target_plan_ids: set[int] = set()

        for item in plans_data:
            plan_id = item["plan_id"]
            target_plan_ids.add(plan_id)
            if plan_id in existing_map:
                assoc = existing_map[plan_id]
                assoc.is_active = item["is_active"]
                assoc.priority = item["priority"]
                assoc.updated_at = datetime.now()
                self.session.add(assoc)
                continue
            self.session.add(
                AccountTaskPlan(
                    account_id=account_id,
                    task_plan_id=plan_id,
                    is_active=item["is_active"],
                    priority=item["priority"],
                )
            )

        for assoc in existing_assocs:
            if assoc.task_plan_id not in target_plan_ids:
                self.session.delete(assoc)

        self._finish_write()
        return True
