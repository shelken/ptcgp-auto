# -*- coding: utf-8 -*-
"""
Notification 模型

存储站内通知记录。
"""

from datetime import datetime
from typing import Optional

from sqlmodel import Field, SQLModel


class Notification(SQLModel, table=True):
    """
    通知记录模型

    存储所有通知记录，支持站内通知和企业微信推送。
    """

    __tablename__ = "notifications"

    id: Optional[int] = Field(default=None, primary_key=True)
    scene: str = Field(
        description="场景名称: rare_card_obtained/task_status/system_warning"
    )
    title: str = Field(description="通知标题")
    content: str = Field(description="Markdown 内容")
    related_account_id: Optional[int] = Field(default=None, description="关联账号 ID")
    related_task_instance_id: Optional[int] = Field(
        default=None, description="关联任务实例 ID"
    )
    is_read: bool = Field(default=False, description="已读状态")
    created_at: datetime = Field(
        default_factory=datetime.now, description="创建时间（本地时间）"
    )
