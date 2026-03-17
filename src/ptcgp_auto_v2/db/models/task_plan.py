# -*- coding: utf-8 -*-
"""
TaskPlan 模型

定义任务计划，指定账号应执行的任务列表。
"""

import json
from datetime import datetime
from typing import TYPE_CHECKING, List, Optional

from sqlmodel import Field, SQLModel

if TYPE_CHECKING:
    pass


class TaskPlan(SQLModel, table=True):
    """
    任务计划模型

    定义账号应执行的任务列表。
    """

    __tablename__ = "task_plans"

    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(unique=True)
    description: Optional[str] = None
    task_types: str = Field(default="[]")  # JSON 数组: ["open_pack", "send_gift"]
    configuration: str = Field(
        default="{}"
    )  # JSON 对象: {"open_pack": {"reset_type": "interval", "interval": 3600}}
    is_global: bool = Field(default=False, description="是否为全局默认计划")
    created_at: datetime = Field(default_factory=datetime.now)

    # 关系
    # 移除旧的 accounts 关系（因为 Account.task_plan_id 已移除）
    # 新的多对多关系（通过关联表）
    # account_associations: List["AccountTaskPlan"] = Relationship()  # 暂时不在 SQLModel 中强类型定义反向关系以免循环依赖问题，主要在 Account 侧定义

    @property
    def config_dict(self) -> dict:
        """将 configuration JSON 解析为字典"""
        if not self.configuration:
            return {}
        try:
            return json.loads(self.configuration)
        except (json.JSONDecodeError, TypeError):
            return {}

    @property
    def task_types_list(self) -> List[str]:
        """将 task_types JSON 解析为列表"""
        if not self.task_types:
            return []
        try:
            return json.loads(self.task_types)
        except (json.JSONDecodeError, TypeError):
            return []

    def task_types_json(self) -> str:
        """将 task_types 列表转换为 JSON 字符串（兼容旧接口）"""
        return self.task_types

    def to_dict(self) -> dict:
        """转换为字典"""
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "task_types": self.task_types_list,
            "configuration": self.config_dict,
            "is_global": self.is_global,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
