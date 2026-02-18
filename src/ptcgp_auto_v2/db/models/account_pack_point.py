# -*- coding: utf-8 -*-
from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlmodel import Field, Relationship, SQLModel

if TYPE_CHECKING:
    from .account import Account


class AccountPackPoint(SQLModel, table=True):
    """
    账号开包点数记录 (Pack Points)
    记录每个账号在不同系列（Series）下的开包点数（pt）。
    """

    __tablename__ = "account_pack_points"  # type: ignore

    # 使用复合主键 (account_id + series) 确保每个账号每个系列只有一条记录
    account_id: int = Field(primary_key=True, index=True)
    series: str = Field(description="系列代码，如 A1", primary_key=True)

    points: int = Field(description="当前点数")
    updated_at: datetime = Field(default_factory=datetime.now)

    account: Optional["Account"] = Relationship(
        sa_relationship_kwargs={
            "primaryjoin": "AccountPackPoint.account_id==Account.id",
            "foreign_keys": "[AccountPackPoint.account_id]",
            "overlaps": "pack_points",
        }
    )
