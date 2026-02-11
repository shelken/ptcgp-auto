# -*- coding: utf-8 -*-
"""
账号送卡配对模型。

用于维护系统内账号之间稳定的每日送卡关系。
"""

from typing import Optional, ClassVar

from sqlalchemy import UniqueConstraint
from sqlmodel import Field, SQLModel

from .base import TimestampMixin


class AccountGiftPair(SQLModel, TimestampMixin, table=True):
    """账号送卡配对关系表。"""

    __tablename__: ClassVar[str] = "account_gift_pairs"
    __table_args__ = (
        UniqueConstraint("account_id", "is_active", name="uq_gift_pair_account_active"),
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    account_id: int = Field(index=True, description="送卡账号ID")
    target_account_id: Optional[int] = Field(
        default=None, index=True, description="目标账号ID（系统内账号）"
    )
    target_friend_id: str = Field(index=True, description="目标账号friend_id")
    strategy: str = Field(default="fixed_card_a1_153", description="配对策略")
    is_active: bool = Field(default=True, index=True, description="是否有效")
