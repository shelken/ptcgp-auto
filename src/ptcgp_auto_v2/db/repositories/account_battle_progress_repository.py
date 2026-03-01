# -*- coding: utf-8 -*-
"""
账号对战进度数据访问层
"""

from datetime import datetime
from typing import Optional

from sqlmodel import Session, select

from ptcgp_auto_v2.db.engine import get_engine
from ptcgp_auto_v2.db.models import AccountBattleProgress


class AccountBattleProgressRepository:
    """账号对战进度数据访问层"""

    def get_progress(
        self, account_id: int, set_code: str, level: str
    ) -> Optional[AccountBattleProgress]:
        """获取指定系列+等级的进度记录"""
        with Session(get_engine()) as session:
            statement = select(AccountBattleProgress).where(
                AccountBattleProgress.account_id == account_id,
                AccountBattleProgress.set_code == set_code,
                AccountBattleProgress.level == level
            )
            return session.exec(statement).first()

    def is_level_completed(self, account_id: int, set_code: str, level: str) -> bool:
        """检查指定系列+等级是否已完成"""
        progress = self.get_progress(account_id, set_code, level)
        return progress is not None and progress.status == "completed"

    def mark_completed(self, account_id: int, set_code: str, level: str) -> bool:
        """标记指定系列+等级为已完成"""
        with Session(get_engine()) as session:
            statement = select(AccountBattleProgress).where(
                AccountBattleProgress.account_id == account_id,
                AccountBattleProgress.set_code == set_code,
                AccountBattleProgress.level == level
            )
            record = session.exec(statement).first()

            if record:
                record.status = "completed"
                record.updated_at = datetime.now()
                session.add(record)
            else:
                record = AccountBattleProgress(
                    account_id=account_id,
                    set_code=set_code,
                    level=level,
                    status="completed"
                )
                session.add(record)

            session.commit()
            return True

    def get_incomplete_levels(
        self, account_id: int, set_code: str
    ) -> list[AccountBattleProgress]:
        """获取指定系列下所有未完成的等级"""
        with Session(get_engine()) as session:
            statement = select(AccountBattleProgress).where(
                AccountBattleProgress.account_id == account_id,
                AccountBattleProgress.set_code == set_code,
                AccountBattleProgress.status == "in_progress"
            )
            return list(session.exec(statement).all())

    def get_all_progress(self, account_id: int) -> list[AccountBattleProgress]:
        """获取账号所有对战进度"""
        with Session(get_engine()) as session:
            statement = select(AccountBattleProgress).where(
                AccountBattleProgress.account_id == account_id
            )
            return list(session.exec(statement).all())
