# -*- coding: utf-8 -*-
"""
PackRecord 模型

记录账号的开包历史。
"""

from datetime import datetime
from typing import TYPE_CHECKING, ClassVar, Optional

from sqlmodel import Field, Relationship, SQLModel

if TYPE_CHECKING:
    from .account import Account
    from .pack_card import PackCard


class PackRecord(SQLModel, table=True):
    """
    开包记录模型

    记录账号的开包历史。
    """

    __tablename__ = "pack_records"  # type: ignore

    id: Optional[int] = Field(default=None, primary_key=True)
    account_id: int = Field(foreign_key="accounts.id")
    pack_type: str = Field(default="")

    # 新增字段：将原 pack_type 拆分为 code 和 name
    pack_code: Optional[str] = Field(default=None, description="系列代码，如 A1")
    pack_name: Optional[str] = Field(default=None, description="卡包名称，如 Charizard")

    opened_at: datetime = Field(default_factory=datetime.now)

    # 关系
    account: Optional["Account"] = Relationship(back_populates="pack_records")
    cards: list["PackCard"] = Relationship(back_populates="pack_record", sa_relationship_kwargs={"cascade": "all, delete-orphan"})

    def to_dict(self) -> dict:
        """转换为字典"""
        return {
            "id": self.id,
            "account_id": self.account_id,
            "pack_type": self.pack_type,
            "pack_code": self.pack_code,
            "pack_name": self.pack_name,
            "opened_at": self.opened_at.isoformat() if self.opened_at else None,
        }
