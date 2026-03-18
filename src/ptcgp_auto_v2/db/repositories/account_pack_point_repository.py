# -*- coding: utf-8 -*-
from datetime import datetime

from sqlmodel import select

from ptcgp_auto_v2.db.models import AccountPackPoint
from .base import BaseRepository


class AccountPackPointRepository(BaseRepository):
    """开包点数数据访问层"""

    def upsert_points(self, account_id: int, series: str, points: int) -> bool:
        """更新或插入开包点数"""
        statement = select(AccountPackPoint).where(
            AccountPackPoint.account_id == account_id,
            AccountPackPoint.series == series,
        )
        record = self.session.exec(statement).first()

        if record:
            record.points = points
            record.updated_at = datetime.now()
            self.session.add(record)
        else:
            record = AccountPackPoint(
                account_id=account_id,
                series=series,
                points=points,
            )
            self.session.add(record)

        self._finish_write(record)
        return True
