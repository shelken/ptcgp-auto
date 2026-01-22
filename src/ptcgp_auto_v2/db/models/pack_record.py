# -*- coding: utf-8 -*-
"""
PackRecord 模型

记录账号的开包历史。
"""

from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlmodel import Field, Relationship, SQLModel

if TYPE_CHECKING:
    from .account import Account


class PackRecord(SQLModel, table=True):
    """
    开包记录模型

    记录账号的开包历史。
    """

    __tablename__ = "pack_records"

    id: Optional[int] = Field(default=None, primary_key=True)
    account_id: int = Field(foreign_key="accounts.id")
    pack_type: str = Field(default="")
    opened_at: datetime = Field(default_factory=datetime.now)

    # 关系
    account: Optional["Account"] = Relationship(back_populates="pack_records")

    def to_dict(self) -> dict:
        """转换为字典"""
        return {
            "id": self.id,
            "account_id": self.account_id,
            "pack_type": self.pack_type,
            "opened_at": self.opened_at.isoformat() if self.opened_at else None,
        }
