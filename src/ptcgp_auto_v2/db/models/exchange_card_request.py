# -*- coding: utf-8 -*-
"""
ExchangeCardRequest 模型

记录交换卡牌请求的完整生命周期。
"""

from datetime import datetime
from typing import Optional

from sqlmodel import Field, SQLModel


class ExchangeCardRequest(SQLModel, table=True):
    """交换卡牌请求记录。"""

    __tablename__ = "exchange_card_requests"  # type: ignore[assignment]

    id: Optional[int] = Field(default=None, primary_key=True)
    from_account_id: int = Field(index=True, description="发起方账号ID")
    to_account_id: Optional[int] = Field(
        default=None, index=True, description="目标账号ID"
    )
    to_friend_id: str = Field(index=True, description="目标 friend_id")
    to_nickname: Optional[str] = Field(default=None, description="目标昵称")
    target_card_id: int = Field(index=True, description="目标卡牌ID")
    target_card_rarity: str = Field(description="目标卡牌稀有度")

    # 状态流转：sending -> sended -> completed/failed/canceled
    status: str = Field(default="sending", index=True, description="请求状态")
    failed_reason: Optional[str] = Field(default=None, description="失败原因")
    cancel_reason: Optional[str] = Field(default=None, description="取消原因")

    # 延时复查窗口
    next_check_at: Optional[datetime] = Field(default=None, index=True)
    expire_at: Optional[datetime] = Field(default=None)

    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)
