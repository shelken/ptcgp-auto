# -*- coding: utf-8 -*-
"""
账号送卡执行记录模型。

用于记录每日送卡执行状态、目标和库存同步信息。
"""

from datetime import datetime
from typing import Optional, ClassVar

from sqlalchemy import UniqueConstraint
from sqlmodel import Field, SQLModel

from .base import TimestampMixin


def _today_local_date() -> str:
    """返回本地日期字符串 YYYY-MM-DD。"""
    return datetime.now().strftime("%Y-%m-%d")


class AccountGiftRecord(SQLModel, TimestampMixin, table=True):
    """账号送卡执行记录表。"""

    __tablename__: ClassVar[str] = "account_gift_records"
    __table_args__ = (
        UniqueConstraint(
            "account_id",
            "target_friend_id",
            "biz_date_local",
            name="uq_gift_record_account_target_day",
        ),
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    account_id: int = Field(index=True, description="送卡账号ID")
    target_account_id: Optional[int] = Field(
        default=None, index=True, description="目标账号ID（系统内账号）"
    )
    target_friend_id: str = Field(index=True, description="目标账号friend_id")

    card_id: Optional[int] = Field(default=None, index=True, description="送出的卡牌ID")
    card_set_code: Optional[str] = Field(default=None, description="送出的卡牌系列代码")
    card_number: Optional[int] = Field(default=None, description="送出的卡牌编号")

    before_count: Optional[int] = Field(default=None, description="送卡前持有数量")
    after_count: Optional[int] = Field(default=None, description="送卡后持有数量")
    count_source: Optional[str] = Field(
        default=None, description="数量来源(ui/fallback/db)"
    )

    status: str = Field(default="init", index=True, description="送卡状态")
    error_code: Optional[str] = Field(
        default=None, index=True, description="失败错误码"
    )
    error_message: Optional[str] = Field(default=None, description="失败详情")

    biz_date_local: str = Field(
        default_factory=_today_local_date,
        index=True,
        description="业务日期（本地日期）",
    )
