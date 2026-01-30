# -*- coding: utf-8 -*-
from datetime import datetime
from typing import Any, List, Optional, cast

from sqlalchemy.orm import selectinload
from sqlmodel import Session, col, func, select

from ptcgp_auto_v2.db.engine import get_engine
from ptcgp_auto_v2.db.models import Account, AccountTaskPlan, TaskPlan


class AccountRepository:
    """账号数据访问层"""

    def get_by_id(self, account_id: int) -> Optional[Account]:
        """根据 ID 获取账号"""
        with Session(get_engine()) as session:
            statement = (
                select(Account)
                .where(Account.id == account_id)
                .options(
                    selectinload(
                        cast(Any, Account.task_plan_associations)
                    ).selectinload(cast(Any, AccountTaskPlan.task_plan)),
                )
            )
            return session.exec(statement).first()

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
            statement = (
                select(Account)
                .options(
                    selectinload(
                        cast(Any, Account.task_plan_associations)
                    ).selectinload(cast(Any, AccountTaskPlan.task_plan)),
                )
                .order_by(col(Account.id))
            )
            return list(session.exec(statement).all())

    def count_all(self) -> int:
        """统计所有账号数量"""
        with Session(get_engine()) as session:
            statement = select(func.count()).select_from(Account)
            result = session.exec(statement).one()
            return result or 0

    def get_accounts_without_friend_id(self) -> List[Account]:
        """获取所有没有 friend_id 的账号（用于补全任务）"""
        with Session(get_engine()) as session:
            statement = (
                select(Account)
                .where((col(Account.friend_id).is_(None)) | (Account.friend_id == ""))
                .order_by(col(Account.id))
            )
            return list(session.exec(statement).all())

    def get_accounts_with_plans(self) -> List[Account]:
        """获取所有有任务计划的账号（包括新旧关联）"""
        with Session(get_engine()) as session:
            # 查询有旧关联 OR 有新关联的账号
            # 这里简化处理：获取所有账号，然后由应用层判断（因为 eager load 了，性能损耗主要在 DB IO）
            # 或者使用 join 过滤。为保持代码简单且健壮，复用 get_all 的 eager load 逻辑
            # 但为了性能，还是加上 where
            statement = (
                select(Account)
                .options(
                    selectinload(
                        cast(Any, Account.task_plan_associations)
                    ).selectinload(cast(Any, AccountTaskPlan.task_plan)),
                )
                .order_by(col(Account.id))
            )
            accounts = list(session.exec(statement).all())
            return accounts

    def create(self, account: Account, auto_assign_plan: bool = True) -> Account:
        """创建账号

        Args:
            account: 账号对象
            auto_assign_plan: 是否自动分配 base 计划（默认 True）。
                              在新账号初始化流程中应设为 False，待 init_account 完成后再分配。
        """
        with Session(get_engine()) as session:
            session.add(account)
            session.commit()
            session.refresh(account)

            # 如果没有指定计划且允许自动分配，关联 "base"
            if auto_assign_plan and not account.task_plan_associations:
                base_plan = self.get_plan_by_name(session, "base")
                if base_plan and account.id is not None and base_plan.id is not None:
                    new_assoc = AccountTaskPlan(
                        account_id=account.id,
                        task_plan_id=base_plan.id,
                        priority=0,
                        is_active=True,
                    )
                    session.add(new_assoc)
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
            db_account.exchange_points = account.exchange_points
            db_account.country = account.country
            db_account.xml_content = account.xml_content
            db_account.session_token_iat = account.session_token_iat
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
        """为账号分配主任务计划（设置为最高优先级）"""
        # 复用 add_secondary_plan，设置较高的优先级 (10)
        return self.add_secondary_plan(account_id, plan_id, priority=10)

    def add_secondary_plan(
        self, account_id: int, plan_id: int, priority: int = 0
    ) -> bool:
        """
        为账号添加额外的任务计划（新接口）

        Args:
            account_id: 账号 ID
            plan_id: 计划 ID
            priority: 优先级

        Returns:
            True 表示成功
        """
        with Session(get_engine()) as session:
            # 检查是否已存在
            statement = select(AccountTaskPlan).where(
                AccountTaskPlan.account_id == account_id,
                AccountTaskPlan.task_plan_id == plan_id,
            )
            existing = session.exec(statement).first()
            if existing:
                existing.is_active = True
                existing.priority = priority
                existing.updated_at = datetime.now()
                session.add(existing)
            else:
                new_assoc = AccountTaskPlan(
                    account_id=account_id,
                    task_plan_id=plan_id,
                    priority=priority,
                )
                session.add(new_assoc)

            session.commit()
            return True

    def remove_secondary_plan(self, account_id: int, plan_id: int) -> bool:
        """移除账号的额外计划"""
        with Session(get_engine()) as session:
            statement = select(AccountTaskPlan).where(
                AccountTaskPlan.account_id == account_id,
                AccountTaskPlan.task_plan_id == plan_id,
            )
            existing = session.exec(statement).first()
            if existing:
                session.delete(existing)
                session.commit()
                return True
            return False

    def update_plan_associations(self, account_id: int, plans_data: List[dict]) -> bool:
        """
        批量更新账号的任务计划关联

        Args:
            account_id: 账号 ID
            plans_data: 计划数据列表，格式: [{"plan_id": int, "is_active": bool, "priority": int}]

        Returns:
            True 表示成功
        """
        with Session(get_engine()) as session:
            # 1. 获取现有关联
            stmt = select(AccountTaskPlan).where(
                AccountTaskPlan.account_id == account_id
            )
            existing_assocs = session.exec(stmt).all()
            existing_map = {assoc.task_plan_id: assoc for assoc in existing_assocs}

            # 2. 处理更新和新增
            target_plan_ids = set()

            for item in plans_data:
                plan_id = item["plan_id"]
                target_plan_ids.add(plan_id)

                if plan_id in existing_map:
                    # 更新
                    assoc = existing_map[plan_id]
                    assoc.is_active = item["is_active"]
                    assoc.priority = item["priority"]
                    assoc.updated_at = datetime.now()
                    session.add(assoc)
                else:
                    # 新增
                    new_assoc = AccountTaskPlan(
                        account_id=account_id,
                        task_plan_id=plan_id,
                        is_active=item["is_active"],
                        priority=item["priority"],
                    )
                    session.add(new_assoc)

            # 3. 处理删除 (在数据库中存在但不在目标列表中的)
            for assoc in existing_assocs:
                if assoc.task_plan_id not in target_plan_ids:
                    session.delete(assoc)

            session.commit()
            return True
