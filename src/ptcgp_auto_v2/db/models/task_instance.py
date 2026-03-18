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
    account_id: int = Field(index=True, description="所属账号 ID，用于关联具体执行账号")
    task_type: str = Field(description="任务类型标识，如 open_pack / send_card_daily")
    status: str = Field(
        default="pending",
        description="任务实例当前状态：pending/running/completed/failed/skipped/blocked",
    )
    reset_type: str = Field(
        default="daily",
        description="任务重置规则：daily/weekly/once/interval",
    )
    error_message: Optional[str] = Field(
        default=None,
        description="最近一次收敛时记录的错误、跳过或完成原因",
    )
    last_completed_at: Optional[datetime] = Field(
        default=None,
        description="展示用途：最近一次真实完成时间；特殊 completed 场景可保留旧值",
    )
    schedule_anchor_at: Optional[datetime] = Field(
        default=None,
        description="调度用途：本次完成用于计算重置/下次运行的时间锚点",
    )
    last_duration_seconds: Optional[int] = Field(
        default=None,
        description="任务实例上一次自身执行耗时（秒）",
    )
    next_run_at: Optional[datetime] = Field(
        default=None,
        description="派生缓存：按当前锚点与重置规则计算出的下次可运行时间",
    )
    created_at: datetime = Field(
        default_factory=datetime.now,
        description="任务实例创建时间",
    )
    updated_at: datetime = Field(
        default_factory=datetime.now,
        description="任务实例最近一次写库时间",
    )

    # 关系
    account: Optional["Account"] = Relationship(
        back_populates="task_instances",
        sa_relationship_kwargs={
            "primaryjoin": "TaskInstance.account_id==Account.id",
            "foreign_keys": "[TaskInstance.account_id]",
        },
    )

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
            "schedule_anchor_at": (
                self.schedule_anchor_at.isoformat()
                if self.schedule_anchor_at
                else None
            ),
            "last_duration_seconds": self.last_duration_seconds,
            "next_run_at": self.next_run_at.isoformat() if self.next_run_at else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
