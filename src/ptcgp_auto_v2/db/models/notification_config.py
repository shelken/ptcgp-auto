# -*- coding: utf-8 -*-
"""
NotificationConfig 模型

存储通知配置，控制各场景的启用状态和扩展参数。
"""

from datetime import datetime
from typing import Optional

from sqlmodel import Field, SQLModel


class NotificationConfig(SQLModel, table=True):
    """
    通知配置模型

    控制各场景的通知启用状态和扩展配置。
    """

    __tablename__ = "notification_configs"

    id: Optional[int] = Field(default=None, primary_key=True)
    scene: str = Field(unique=True, description="场景名称（唯一）")
    enabled: bool = Field(default=True, description="是否启用站内通知")
    enabled_webhook: bool = Field(default=False, description="是否启用企微推送")
    extra_config: Optional[str] = Field(default="{}", description="扩展配置 JSON")
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)
