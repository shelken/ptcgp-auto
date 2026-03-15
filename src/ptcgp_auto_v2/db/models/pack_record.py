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


class PackRecordType:
    """开包记录类型常量。"""

    DAILY_FREE = "daily_free"
    TEN_PACK = "ten_pack"
    GIFT_BOX = "gift_box"
    INIT_TUTORIAL = "init_tutorial"


class PackRecord(SQLModel, table=True):
    """
    开包记录模型

    记录账号的开包历史。
    """

    __tablename__ = "pack_records"  # type: ignore

    id: Optional[int] = Field(default=None, primary_key=True)
    account_id: int = Field(index=True)
    pack_type: str = Field(default="")

    # 数据库存储字段：系列代码，如 A1
    pack_code: Optional[str] = Field(default=None, description="系列代码，如 A1")
    pack_name: Optional[str] = Field(default=None, description="卡包名称，如 Charizard")

    # 批次字段：用于关联十连包
    batch_id: Optional[str] = Field(
        default=None, index=True, description="批次ID，同一批十连包共享此ID"
    )
    batch_index: Optional[int] = Field(
        default=None, description="批次内序号，十连包为1-10"
    )

    opened_at: datetime = Field(default_factory=datetime.now)

    # 关系
    account: Optional["Account"] = Relationship(
        back_populates="pack_records",
        sa_relationship_kwargs={
            "primaryjoin": "PackRecord.account_id==Account.id",
            "foreign_keys": "[PackRecord.account_id]",
        },
    )
    cards: list["PackCard"] = Relationship(
        back_populates="pack_record",
        sa_relationship_kwargs={
            "cascade": "all, delete-orphan",
            "primaryjoin": "PackRecord.id==PackCard.pack_record_id",
            "foreign_keys": "[PackCard.pack_record_id]",
        },
    )

    @property
    def set_code(self) -> Optional[str]:
        """业务语义中的系列代码。"""
        return self.pack_code

    @set_code.setter
    def set_code(self, value: Optional[str]) -> None:
        """将业务语义 set_code 映射回数据库字段。"""
        self.pack_code = value

    def to_dict(self) -> dict:
        """转换为字典"""
        return {
            "id": self.id,
            "account_id": self.account_id,
            "pack_type": self.pack_type,
            "set_code": self.set_code,
            "pack_name": self.pack_name,
            "batch_id": self.batch_id,
            "batch_index": self.batch_index,
            "opened_at": self.opened_at.isoformat() if self.opened_at else None,
        }
