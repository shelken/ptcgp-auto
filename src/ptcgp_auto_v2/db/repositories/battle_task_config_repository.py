# -*- coding: utf-8 -*-
"""
对战任务配置数据访问层
"""

import json
from typing import Optional

from sqlmodel import select

from ptcgp_auto_v2.db.models import BattleTaskConfig
from .base import BaseRepository


class BattleTaskConfigRepository(BaseRepository):
    """对战任务配置数据访问层"""

    def get_by_task_instance(self, task_instance_id: int) -> Optional[BattleTaskConfig]:
        """根据任务实例ID获取配置"""
        statement = select(BattleTaskConfig).where(
            BattleTaskConfig.task_instance_id == task_instance_id
        )
        return self.session.exec(statement).first()

    def get_by_account(self, account_id: int) -> list[BattleTaskConfig]:
        """获取账号的所有对战任务配置"""
        statement = select(BattleTaskConfig).where(
            BattleTaskConfig.account_id == account_id
        )
        return list(self.session.exec(statement).all())

    def create_config(
        self, account_id: int, task_instance_id: int, stop_conditions: list[dict]
    ) -> BattleTaskConfig:
        """创建对战任务配置"""
        config = BattleTaskConfig(
            account_id=account_id,
            task_instance_id=task_instance_id,
            stop_conditions=json.dumps(stop_conditions),
        )
        self.session.add(config)
        self._finish_write(config)
        return config

    def get_stop_conditions(self, task_instance_id: int) -> list[dict]:
        """获取停止条件配置"""
        config = self.get_by_task_instance(task_instance_id)
        if not config:
            return []
        try:
            return json.loads(config.stop_conditions)
        except json.JSONDecodeError:
            return []
