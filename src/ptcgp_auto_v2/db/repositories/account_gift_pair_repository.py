# -*- coding: utf-8 -*-
"""
AccountGiftPairRepository

送卡配对关系数据访问层。
"""

from datetime import datetime
from typing import Optional

from sqlalchemy import update
from sqlmodel import col, select

from ptcgp_auto_v2.db.models import AccountGiftPair
from .base import BaseRepository


class AccountGiftPairRepository(BaseRepository):
    """送卡配对关系数据访问层。"""

    def get_by_account(self, account_id: int) -> Optional[AccountGiftPair]:
        """获取账号当前送卡配对。"""
        statement = (
            select(AccountGiftPair)
            .where(AccountGiftPair.account_id == account_id)
            .order_by(AccountGiftPair.updated_at.desc(), AccountGiftPair.id.desc())
        )
        return self.session.exec(statement).first()

    def list_all(self) -> list[AccountGiftPair]:
        """获取全部送卡配对。"""
        statement = select(AccountGiftPair).order_by(
            AccountGiftPair.account_id,
            AccountGiftPair.target_account_id,
            AccountGiftPair.id,
        )
        return list(self.session.exec(statement).all())

    def create_if_missing(
        self,
        account_id: int,
        target_friend_id: str,
        target_account_id: Optional[int],
        strategy: str = "fixed_card_a1_153",
    ) -> AccountGiftPair:
        """仅在账号尚无配对时创建。"""
        existing = self.get_by_account(account_id)
        if existing is not None:
            return existing

        record = AccountGiftPair(
            account_id=account_id,
            target_friend_id=target_friend_id,
            target_account_id=target_account_id,
            strategy=strategy,
            is_active=True,
        )
        self.session.add(record)
        self._finish_write(record)
        return record

    def update_target_friend_id(self, pair_id: int, target_friend_id: str) -> bool:
        """刷新单条配对里的目标 friend_id 快照。"""
        record = self.session.get(AccountGiftPair, pair_id)
        if record is None:
            return False
        if record.target_friend_id == target_friend_id:
            return False
        record.target_friend_id = target_friend_id
        record.updated_at = datetime.now()
        self.session.add(record)
        self._finish_write(record)
        return True

    def sync_target_friend_id_by_target_account(
        self,
        target_account_id: int,
        target_friend_id: str,
    ) -> int:
        """按目标账号批量刷新目标 friend_id 快照。"""
        now = datetime.now()
        statement = (
            update(AccountGiftPair)
            .where(
                col(AccountGiftPair.target_account_id) == target_account_id,
                col(AccountGiftPair.target_friend_id) != target_friend_id,
            )
            .values(
                target_friend_id=target_friend_id,
                updated_at=now,
            )
        )
        result = self.session.exec(statement)
        self._finish_write()
        return int(result.rowcount or 0)
