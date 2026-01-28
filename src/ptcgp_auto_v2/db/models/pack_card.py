# -*- coding: utf-8 -*-
"""
PackCard 模型

记录一次开包中包含的具体卡牌明细。
"""

from typing import TYPE_CHECKING, Optional

from sqlmodel import Field, Relationship, SQLModel

if TYPE_CHECKING:
    from .pack_record import PackRecord
    from .card import Card


class PackCard(SQLModel, table=True):
    """
    开包卡牌明细模型
    """

    __tablename__ = "pack_cards"

    id: Optional[int] = Field(default=None, primary_key=True)
    pack_record_id: int = Field(index=True)
    card_id: Optional[int] = Field(default=None, description="关联的卡牌ID", index=True)

    # 冗余字段（方便快速查看，也为了应对无法匹配到 card_id 的情况）
    card_name: str = Field(description="识别到的卡牌名称")
    rarity: Optional[str] = Field(default=None, description="卡牌稀有度")
    is_new: bool = Field(default=False, description="是否是新获得的卡")
    position: int = Field(default=0, description="卡牌在包中的位置(1-based)")
    confidence: float = Field(default=0.0, description="识别置信度")

    # 关系
    pack_record: Optional["PackRecord"] = Relationship(
        back_populates="cards",
        sa_relationship_kwargs={
            "primaryjoin": "PackCard.pack_record_id==PackRecord.id",
            "foreign_keys": "[PackCard.pack_record_id]",
        },
    )
    card: Optional["Card"] = Relationship(
        sa_relationship_kwargs={
            "primaryjoin": "PackCard.card_id==Card.id",
            "foreign_keys": "[PackCard.card_id]",
        },
    )

    def to_dict(self) -> dict:
        return {
            "card_name": self.card_name,
            "rarity": self.rarity,
            "card_id": self.card_id,
            "is_new": self.is_new,
            "position": self.position,
        }
