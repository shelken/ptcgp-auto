# -*- coding: utf-8 -*-
"""
对战任务配置表

用于手动下发对战任务时存储停止条件配置。
通过 account_id 和 task_instance_id 关联。
"""

from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlmodel import Field, Relationship, SQLModel

if TYPE_CHECKING:
    from .account import Account
    from .task_instance import TaskInstance


class BattleTaskConfig(SQLModel, table=True):
    """
    对战任务配置表

    存储对战任务的停止条件配置，支持多种停止条件组合。
    停止条件本身包含目标信息（set_code, level）。
    """

    __tablename__ = "battle_task_config"  # type: ignore

    id: Optional[int] = Field(default=None, primary_key=True)
    account_id: int = Field(index=True, description="关联的账号ID")
    task_instance_id: int = Field(description="关联的任务实例ID")

    # 停止条件配置 (JSON 字符串)
    # 示例：
    # [{"type": "level_complete", "set_code": "A1", "level": "精英"}]
    # [{"type": "time", "value": 30}, {"type": "hourglass", "value": 3}]
    stop_conditions: str = Field(
        default="[]",
        description="停止条件配置(JSON)，包含目标信息和停止条件"
    )

    created_at: datetime = Field(
        default_factory=datetime.now,
        description="创建时间"
    )

    # 关系定义
    account: Optional["Account"] = Relationship(
        sa_relationship_kwargs={
            "primaryjoin": "BattleTaskConfig.account_id==Account.id",
            "foreign_keys": "[BattleTaskConfig.account_id]",
        }
    )

    task_instance: Optional["TaskInstance"] = Relationship(
        sa_relationship_kwargs={
            "primaryjoin": "BattleTaskConfig.task_instance_id==TaskInstance.id",
            "foreign_keys": "[BattleTaskConfig.task_instance_id]",
        }
    )
