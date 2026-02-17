# -*- coding: utf-8 -*-
"""
AccountFriendship 模型

记录已建立的好友关系。
"""

from datetime import datetime
from typing import ClassVar, Optional

from sqlalchemy import UniqueConstraint
from sqlmodel import Field, SQLModel


class AccountFriendship(SQLModel, table=True):
    """
    好友关系表

    记录已建立的好友关系。
    双向关系需要两条记录（A→B 和 B→A）。
    """

    __tablename__: ClassVar[str] = "account_friendships"
    __table_args__ = (UniqueConstraint("account_id", "friend_id"),)

    id: Optional[int] = Field(default=None, primary_key=True)

    # 账号 A 的 ID
    account_id: int = Field(index=True, description="账号ID")

    # 账号 B 的 friend_id（游戏内可见）
    friend_id: str = Field(index=True, description="好友的friend_id")

    # 账号 B 的 account_id（如果 B 也是系统内账号，可选）
    friend_account_id: Optional[int] = Field(
        default=None,
        description="好友的账号ID（系统内账号有值）",
    )

    # 好友昵称（系统外账号从游戏获取）
    friend_nickname: Optional[str] = Field(
        default=None,
        description="好友昵称（系统外账号从游戏获取）",
    )

    # 时间戳（本地时间）
    created_at: datetime = Field(default_factory=datetime.now)
