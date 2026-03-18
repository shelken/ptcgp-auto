# -*- coding: utf-8 -*-
"""
AccountGiftPairRepository

送卡配对关系数据访问层。
"""

from datetime import datetime
from typing import Optional

from sqlmodel import select

from ptcgp_auto_v2.db.models import AccountGiftPair
from .base import BaseRepository


class AccountGiftPairRepository(BaseRepository):
    """送卡配对关系数据访问层。"""

    def get_active_by_account(self, account_id: int) -> Optional[AccountGiftPair]:
        """获取账号当前有效配对。"""
        statement = select(AccountGiftPair).where(
            AccountGiftPair.account_id == account_id,
            AccountGiftPair.is_active.is_(True),
        )
        return self.session.exec(statement).first()

    def get_all_active(self) -> list[AccountGiftPair]:
        """获取全部有效配对。"""
        statement = select(AccountGiftPair).where(AccountGiftPair.is_active.is_(True))
        return list(self.session.exec(statement).all())

    def upsert_active_pair(
        self,
        account_id: int,
        target_friend_id: str,
        target_account_id: Optional[int],
        strategy: str = "fixed_card_a1_153",
    ) -> AccountGiftPair:
        """写入或更新有效配对。"""
        statement = select(AccountGiftPair).where(
            AccountGiftPair.account_id == account_id,
            AccountGiftPair.is_active.is_(True),
        )
        existing = self.session.exec(statement).first()
        if existing:
            existing.target_friend_id = target_friend_id
            existing.target_account_id = target_account_id
            existing.strategy = strategy
            existing.updated_at = datetime.now()
            self.session.add(existing)
            self._finish_write(existing)
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

    def deactivate_active_pair(self, account_id: int) -> bool:
        """失效账号当前有效配对。"""
        statement = select(AccountGiftPair).where(
            AccountGiftPair.account_id == account_id,
            AccountGiftPair.is_active.is_(True),
        )
        existing = self.session.exec(statement).first()
        if not existing:
            return False
        existing.is_active = False
        existing.updated_at = datetime.now()
        self.session.add(existing)
        self._finish_write()
        return True
