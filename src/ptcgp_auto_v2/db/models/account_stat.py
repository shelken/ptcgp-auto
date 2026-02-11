# -*- coding: utf-8 -*-
"""
账号统计模型

用于存储账号维度的资源统计数据（如交换点数、开包沙漏）。
"""

from typing import Optional

from sqlmodel import Field, SQLModel

from .base import TimestampMixin


class AccountStat(SQLModel, TimestampMixin, table=True):
    """账号资源统计表。"""

    __tablename__ = "account_stats"

    account_id: int = Field(primary_key=True, index=True, description="账号ID")
    exchange_points: Optional[int] = Field(default=None, description="交换点数")
    pack_hourglass_count: Optional[int] = Field(
        default=None, description="开包沙漏数量"
    )
