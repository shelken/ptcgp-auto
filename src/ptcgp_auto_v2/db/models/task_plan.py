# -*- coding: utf-8 -*-
"""
TaskPlan 模型

定义任务计划，指定账号应执行的任务列表。
"""

import json
from datetime import datetime
from typing import TYPE_CHECKING, List, Optional

from sqlmodel import Field, Relationship, SQLModel

if TYPE_CHECKING:
    from .account import Account


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
    created_at: datetime = Field(default_factory=datetime.now)

    # 关系
    accounts: List["Account"] = Relationship(back_populates="task_plan")

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
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
