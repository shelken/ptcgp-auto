# -*- coding: utf-8 -*-
"""
账号统计数据访问层
"""

from datetime import datetime
from typing import Optional

from sqlmodel import Session

from ptcgp_auto_v2.db.engine import get_engine
from ptcgp_auto_v2.db.models import AccountStat


class AccountStatRepository:
    """账号统计仓储。"""

    def get_by_account_id(self, account_id: int) -> Optional[AccountStat]:
        """按账号ID读取统计信息。"""
        with Session(get_engine()) as session:
            return session.get(AccountStat, account_id)

    def upsert(
        self,
        account_id: int,
        exchange_points: Optional[int] = None,
        pack_hourglass_count: Optional[int] = None,
    ) -> AccountStat:
        """写入或更新账号统计信息。"""
        with Session(get_engine()) as session:
            row = session.get(AccountStat, account_id)
            if row is None:
                row = AccountStat(
                    account_id=account_id,
                    exchange_points=exchange_points,
                    pack_hourglass_count=pack_hourglass_count,
                )
            else:
                row.exchange_points = exchange_points
                row.pack_hourglass_count = pack_hourglass_count
                row.updated_at = datetime.now()

            session.add(row)
            session.commit()
            session.refresh(row)
            return row

    def decrease_pack_hourglass_count(
        self, account_id: int, amount: int
    ) -> Optional[AccountStat]:
        """扣减开包沙漏数量，最少为 0。"""
        if amount <= 0:
            return self.get_by_account_id(account_id)

        with Session(get_engine()) as session:
            row = session.get(AccountStat, account_id)
            if row is None or row.pack_hourglass_count is None:
                return row

            row.pack_hourglass_count = max(0, row.pack_hourglass_count - amount)
            row.updated_at = datetime.now()
            session.add(row)
            session.commit()
            session.refresh(row)
            return row
