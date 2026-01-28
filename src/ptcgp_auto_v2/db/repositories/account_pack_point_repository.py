# -*- coding: utf-8 -*-
from datetime import datetime

from sqlmodel import Session, select

from ptcgp_auto_v2.db.engine import get_engine
from ptcgp_auto_v2.db.models import AccountPackPoint


class AccountPackPointRepository:
    """开包点数数据访问层"""

    def upsert_points(self, account_id: int, series: str, points: int) -> bool:
        """更新或插入开包点数"""
        with Session(get_engine()) as session:
            statement = select(AccountPackPoint).where(
                AccountPackPoint.account_id == account_id,
                AccountPackPoint.series == series
            )
            record = session.exec(statement).first()

            if record:
                # 更新现有记录
                record.points = points
                record.updated_at = datetime.now()
                session.add(record)
            else:
                # 创建新记录
                record = AccountPackPoint(
                    account_id=account_id,
                    series=series,
                    points=points
                )
                session.add(record)

            session.commit()
            return True