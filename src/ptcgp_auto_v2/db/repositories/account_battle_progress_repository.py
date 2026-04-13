# -*- coding: utf-8 -*-
"""
账号对战进度数据访问层
"""

from datetime import datetime
from typing import Optional

from sqlmodel import select

from ptcgp_auto_v2.db.models import AccountBattleProgress
from .base import BaseRepository


class AccountBattleProgressRepository(BaseRepository):
    """账号对战进度数据访问层"""

    def get_progress(
        self, account_id: int, set_code: str, level: str
    ) -> Optional[AccountBattleProgress]:
        """获取指定系列+等级的进度记录"""
        statement = select(AccountBattleProgress).where(
            AccountBattleProgress.account_id == account_id,
            AccountBattleProgress.set_code == set_code,
            AccountBattleProgress.level == level,
        )
        return self.session.exec(statement).first()

    def is_level_completed(self, account_id: int, set_code: str, level: str) -> bool:
        """检查指定系列+等级是否已完成"""
        progress = self.get_progress(account_id, set_code, level)
        return progress is not None and progress.status == "completed"

    def mark_completed(self, account_id: int, set_code: str, level: str) -> bool:
        """标记指定系列+等级为已完成"""
        statement = select(AccountBattleProgress).where(
            AccountBattleProgress.account_id == account_id,
            AccountBattleProgress.set_code == set_code,
            AccountBattleProgress.level == level,
        )
        record = self.session.exec(statement).first()

        if record:
            record.status = "completed"
            record.updated_at = datetime.now()
            self.session.add(record)
        else:
            record = AccountBattleProgress(
                account_id=account_id,
                set_code=set_code,
                level=level,
                status="completed",
            )
            self.session.add(record)

        self._finish_write(record)
        return True
