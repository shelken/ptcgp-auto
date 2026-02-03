# -*- coding: utf-8 -*-
"""
账号卡牌关联模型
"""

from typing import Optional

from sqlmodel import Field, SQLModel

from .base import TimestampMixin


class AccountCard(SQLModel, TimestampMixin, table=True):
    """账号拥有卡牌关联表"""

    __tablename__ = "account_cards"  # type: ignore[assignment]

    id: Optional[int] = Field(default=None, primary_key=True)
    account_id: int = Field(index=True, description="账号 ID")
    card_id: int = Field(index=True, description="卡牌 ID")
    count: int = Field(default=1, description="拥有数量")
    yolo_conf: Optional[float] = Field(
        default=None, description="YOLO 检测置信度（当前卡牌识别结果）"
    )
    hash_similarity: Optional[float] = Field(
        default=None, description="Hash 匹配相似度（当前卡牌识别结果）"
    )
