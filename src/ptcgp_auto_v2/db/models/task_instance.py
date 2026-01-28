# -*- coding: utf-8 -*-
"""
TaskInstance 模型

表示一个具体的任务执行实例（如账号A的今日开包任务）。
"""

from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlmodel import Field, Relationship, SQLModel

if TYPE_CHECKING:
    from .account import Account


class TaskInstance(SQLModel, table=True):
    """
    任务实例模型

    表示一个具体的任务执行实例。

    状态说明：
    - pending: 待执行
    - running: 执行中
    - completed: 已完成
    - failed: 执行失败
    - skipped: 已跳过（如12小时内已开包）
    - blocked: 被阻塞（等待前置任务）
    """

    __tablename__ = "task_instances"

    id: Optional[int] = Field(default=None, primary_key=True)
    account_id: int = Field(index=True)
    task_type: str
    status: str = Field(
        default="pending",
        description="pending/running/completed/failed/skipped/blocked",
    )
    reset_type: str = Field(default="daily", description="daily/weekly/once")
    error_message: Optional[str] = None
    last_completed_at: Optional[datetime] = None
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)

    # 关系
    account: Optional["Account"] = Relationship(
        back_populates="task_instances",
        sa_relationship_kwargs={
            "primaryjoin": "TaskInstance.account_id==Account.id",
            "foreign_keys": "[TaskInstance.account_id]",
        },
    )

    def save(self):
        """保存到数据库（兼容旧接口）"""
        from ..repositories import TaskInstanceRepository

        TaskInstanceRepository().update(self)

    def to_dict(self) -> dict:
        """转换为字典"""
        return {
            "id": self.id,
            "account_id": self.account_id,
            "task_type": self.task_type,
            "status": self.status,
            "reset_type": self.reset_type,
            "error_message": self.error_message,
            "last_completed_at": (
                self.last_completed_at.isoformat() if self.last_completed_at else None
            ),
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
