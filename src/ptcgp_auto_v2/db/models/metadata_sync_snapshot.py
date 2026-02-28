# -*- coding: utf-8 -*-
"""元数据同步预览快照模型。"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlmodel import Field, SQLModel

from .base import TimestampMixin


class MetadataSyncSnapshot(SQLModel, TimestampMixin, table=True):
    """元数据同步快照，用于预览后确认执行。"""

    __tablename__ = "metadata_sync_snapshots"

    id: Optional[int] = Field(default=None, primary_key=True)
    snapshot_id: str = Field(index=True, description="快照唯一ID")
    scope_level: str = Field(description="同步范围层级: all/set/pack/card")
    scope_value: Optional[str] = Field(default=None, description="范围值")
    source: str = Field(description="来源: flibustier/52poke/full")
    mode: str = Field(description="模式: supplement/force")
    payload_json: str = Field(description="执行载荷JSON")
    summary_json: str = Field(description="预览摘要JSON")
    status: str = Field(default="previewed", description="状态")
    expires_at: datetime = Field(description="快照过期时间")
    executed_at: Optional[datetime] = Field(default=None, description="执行时间")
