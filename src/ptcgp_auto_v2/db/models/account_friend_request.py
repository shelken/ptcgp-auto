# -*- coding: utf-8 -*-
"""
AccountFriendRequest 模型

记录好友请求的完整生命周期（添加/删除）。
"""

from datetime import datetime
from typing import Optional

from sqlmodel import Field, SQLModel


class AccountFriendRequest(SQLModel, table=True):
    """
    好友请求表

    记录好友请求的完整生命周期。
    - add 类型: sending -> sended -> completed/failed
    - delete 类型: deleting -> completed/failed
    """

    __tablename__ = "account_friend_request"  # type: ignore[assignment]

    id: Optional[int] = Field(default=None, primary_key=True)

    # 发送方（必须知道账号 ID）
    from_account_id: int = Field(index=True, description="发送方账号ID")

    # 接收方（可以是账号 ID 或 friend_id）
    to_account_id: Optional[int] = Field(
        default=None,
        description="接收方账号ID（系统内账号）",
    )
    to_friend_id: Optional[str] = Field(
        default=None,
        index=True,
        description="接收方friend_id（外部账号只有这个）",
    )
    to_nickname: Optional[str] = Field(default=None, description="接收方昵称")

    # 请求类型: add(添加) / delete(删除)
    request_type: str = Field(default="add", description="add 或 delete")

    # 状态
    # add 类型: sending -> sended -> completed / failed
    # delete 类型: deleting -> completed / failed
    status: str = Field(default="sending", description="状态")

    # 失败原因
    failed_reason: Optional[str] = None

    # 时间戳（本地时间）
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)
