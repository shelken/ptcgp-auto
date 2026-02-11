# -*- coding: utf-8 -*-
"""
AccountGiftRecordRepository

送卡执行记录数据访问层。
"""

from datetime import datetime
from typing import Optional

from sqlmodel import Session, select

from ptcgp_auto_v2.db.engine import get_engine
from ptcgp_auto_v2.db.models import AccountGiftRecord


class AccountGiftRecordRepository:
    """送卡执行记录数据访问层。"""

    def get_daily_record(
        self,
        account_id: int,
        target_friend_id: str,
        biz_date_local: str,
    ) -> Optional[AccountGiftRecord]:
        """按账号/目标/日期读取单日记录。"""
        with Session(get_engine()) as session:
            statement = select(AccountGiftRecord).where(
                AccountGiftRecord.account_id == account_id,
                AccountGiftRecord.target_friend_id == target_friend_id,
                AccountGiftRecord.biz_date_local == biz_date_local,
            )
            return session.exec(statement).first()

    def get_daily_success_record(
        self,
        account_id: int,
        target_friend_id: str,
        biz_date_local: str,
    ) -> Optional[AccountGiftRecord]:
        """读取单日成功记录。"""
        with Session(get_engine()) as session:
            statement = select(AccountGiftRecord).where(
                AccountGiftRecord.account_id == account_id,
                AccountGiftRecord.target_friend_id == target_friend_id,
                AccountGiftRecord.biz_date_local == biz_date_local,
                AccountGiftRecord.status == "success",
            )
            return session.exec(statement).first()

    def create_or_get_daily(
        self,
        account_id: int,
        target_friend_id: str,
        target_account_id: Optional[int],
        card_set_code: Optional[str],
        card_number: Optional[int],
        biz_date_local: str,
    ) -> AccountGiftRecord:
        """创建或获取单日记录。"""
        with Session(get_engine()) as session:
            statement = select(AccountGiftRecord).where(
                AccountGiftRecord.account_id == account_id,
                AccountGiftRecord.target_friend_id == target_friend_id,
                AccountGiftRecord.biz_date_local == biz_date_local,
            )
            existing = session.exec(statement).first()
            if existing:
                return existing

            record = AccountGiftRecord(
                account_id=account_id,
                target_account_id=target_account_id,
                target_friend_id=target_friend_id,
                card_set_code=card_set_code,
                card_number=card_number,
                biz_date_local=biz_date_local,
                status="init",
            )
            session.add(record)
            session.commit()
            session.refresh(record)
            return record

    def update(self, record: AccountGiftRecord) -> AccountGiftRecord:
        """更新记录。"""
        with Session(get_engine()) as session:
            record.updated_at = datetime.now()
            session.add(record)
            session.commit()
            session.refresh(record)
            return record
