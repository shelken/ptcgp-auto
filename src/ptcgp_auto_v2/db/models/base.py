# -*- coding: utf-8 -*-
"""
SQLModel 基础类和公共工具

提供 SQLModel 模型的基础类和混入类。
"""

from datetime import datetime

from sqlmodel import Field


class TimestampMixin:
    """
    时间戳混入类

    为模型提供 created_at 和 updated_at 字段。
    注意：这是一个混入类，不是独立模型，需与 SQLModel 表类一起使用。
    """

    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)
