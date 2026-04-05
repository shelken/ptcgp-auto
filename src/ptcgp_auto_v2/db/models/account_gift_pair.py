# -*- coding: utf-8 -*-
"""
账号送卡配对模型。

用于维护系统内账号之间稳定的每日送卡关系。
"""

from typing import Optional, ClassVar

from sqlalchemy import Index
from sqlmodel import Field, SQLModel

from .base import TimestampMixin


class AccountGiftPair(SQLModel, TimestampMixin, table=True):
    """
    账号送卡配对关系表。

    第一性语义：
    - 这是 `send_card_daily` 的固定目标映射表，不是执行日志，也不是运行时重排池。
    - 一条记录表示：`account_id` 每日送卡时，应把卡送给哪个系统内账号 / friend_id。
    - 配对缺失时允许补建，但已有 `account_id -> target_account_id` 关系默认保持稳定，不在任务运行时自动失效或改写。
    - `target_friend_id` 是执行快照；目标账号更新 friend_id 后，这个快照允许同步刷新。
    - 业务上通常按双向成对使用，但表约束只保证「每个账号最多一条当前配对」。
    """

    __tablename__: ClassVar[str] = "account_gift_pairs"
    __table_args__ = (
        Index(
            "ux_account_gift_pairs_account",
            "account_id",
            unique=True,
        ),
    )

    id: Optional[int] = Field(
        default=None,
        primary_key=True,
        description="配对记录主键，仅用于表内唯一标识",
    )
    account_id: int = Field(
        index=True,
        description="送卡发起账号 ID；唯一索引建在该字段上，保证每个账号只有一条固定配对",
    )
    target_account_id: Optional[int] = Field(
        default=None,
        index=True,
        description="目标账号 ID（系统内账号）；用于回送唤醒和 Web 侧展示配对关系",
    )
    target_friend_id: str = Field(
        index=True,
        description="目标账号当前 friend_id 执行快照；送卡任务直接用它做页面内好友匹配，目标账号更新 friend_id 后会同步刷新",
    )
    strategy: str = Field(
        default="fixed_card_a1_153",
        description="建立该配对时采用的送卡策略标识；当前固定为送 A1-153",
    )
    is_active: bool = Field(
        default=True,
        index=True,
        description="兼容历史字段；固定配对语义下始终为 True，不再承载启停逻辑",
    )
