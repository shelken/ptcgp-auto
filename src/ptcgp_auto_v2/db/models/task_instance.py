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

    id: Optional[int] = Field(
        default=None,
        primary_key=True,
        description="任务实例主键；同一账号的每种任务共享一条长期记录",
    )
    account_id: int = Field(
        index=True,
        description="所属账号 ID；任务调度、批量派发和异常回收都按账号维度展开",
    )
    task_type: str = Field(
        description="任务类型标识，如 open_pack / send_card_daily；与 account_id 一起决定这条记录表示什么任务",
    )
    status: str = Field(
        default="pending",
        description="任务实例当前状态；运行态切换决定调度是否可派发和异常回收口径",
    )
    reset_type: str = Field(
        default="daily",
        description="任务重置规则；只影响 completed 后何时再次进入 pending，不影响 failed 回收",
    )
    error_message: Optional[str] = Field(
        default=None,
        description="最近一次收敛结果文本；统一承载错误、跳过原因和完成原因",
    )
    status_changed_at: Optional[datetime] = Field(
        default_factory=datetime.now,
        description="任务状态最近一次变化时间；专门给 running/blocked/failed/skipped 超时回收使用，不能再混用 updated_at",
    )
    last_completed_at: Optional[datetime] = Field(
        default=None,
        description="展示用途的最近完成时间；用于页面展示“上次完成”，不参与异常回收",
    )
    schedule_anchor_at: Optional[datetime] = Field(
        default=None,
        description="调度锚点；completed 后按它计算下次 daily/interval 运行时间",
    )
    last_duration_seconds: Optional[int] = Field(
        default=None,
        description="上一次任务自身耗时；用于 Web 展示和排查慢任务",
    )
    next_run_at: Optional[datetime] = Field(
        default=None,
        description="派生缓存；只有 pending 任务会真正用它判断是否到执行窗口",
    )
    created_at: datetime = Field(
        default_factory=datetime.now,
        description="任务实例首次创建时间；表示这条长期任务记录何时入库",
    )
    updated_at: datetime = Field(
        default_factory=datetime.now,
        description="任务实例最近一次任意写库时间；用于审计，不再承担状态超时语义",
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
            "status_changed_at": (
                self.status_changed_at.isoformat() if self.status_changed_at else None
            ),
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
