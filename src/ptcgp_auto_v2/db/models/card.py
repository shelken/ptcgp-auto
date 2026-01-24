# -*- coding: utf-8 -*-
"""
Card 相关模型

包含 CardSet, Card, CardPack 三个模型，用于存储游戏静态数据。
"""

from datetime import datetime
from typing import Optional, List

from sqlmodel import Field, Relationship, SQLModel

from .base import TimestampMixin


class CardSet(SQLModel, TimestampMixin, table=True):
    """
    卡牌系列模型 (如 A1, A2, PROMO-A)
    """

    __tablename__ = "card_sets"

    code: str = Field(primary_key=True, description="系列代码，如 A1")
    name: str = Field(description="系列名称")
    release_date: Optional[str] = Field(default=None, description="发布日期 YYYY-MM-DD")
    total_cards: int = Field(default=0, description="卡牌总数")

    # 关系
    cards: List["Card"] = Relationship(back_populates="card_set")


class Card(SQLModel, TimestampMixin, table=True):
    """
    卡牌模型
    """

    __tablename__ = "cards"

    id: Optional[int] = Field(default=None, primary_key=True)

    # 来源: cards.json 中的 "set" 字段 (例如 "A1")
    # 关联 sets.json 中的 "code"
    set_code: str = Field(foreign_key="card_sets.code", index=True)

    # 来源: cards.json 中的 "number" 字段
    number: int = Field(description="卡牌在系列中的编号")

    # 来源: cards.json 中的 "name" 字段 (英文名称)
    name: str = Field(description="卡牌名称")

    # 来源: cards.json 中的 "rarity" 字段
    # 参考 rarities.json:
    # C: Common / 1钻
    # U: Uncommon / 2钻
    # R: Rare / 3钻
    # RR: Double Rare / 4钻
    # AR: Art Rare / 1星 (异画)
    # SR: Super Rare / 2星 (全图)
    # SAR: Special Art Rare / 2星 (彩虹边/特别异画)
    # IM: Immersive Rare / 3星 (实景/沉浸)
    # UR: Crown Rare / 皇冠 (金卡)
    # S: Shiny / 1闪星 (异色)
    # SSR: Shiny Super Rare / 2闪星 (异色SR)
    rarity: str = Field(description="稀有度代码")

    # 来源: cards.json 中的 "image" 字段 (文件名, 例如 "cPK_10_000010_00_FUSHIGIDANE_C.webp")
    image_url: str = Field(description="远程图片URL")
    local_image_path: Optional[str] = Field(
        default=None, description="本地模板图片路径"
    )
    data: Optional[str] = Field(default=None, description="JSON格式的其他属性")

    # 关系
    card_set: Optional[CardSet] = Relationship(back_populates="cards")
    packs: List["CardPack"] = Relationship(back_populates="card")


class CardPack(SQLModel, TimestampMixin, table=True):
    """
    卡牌-卡包关联模型

    记录一张卡牌属于哪些子包 (如 Mewtwo, Charizard)
    """

    __tablename__ = "card_packs"

    id: Optional[int] = Field(default=None, primary_key=True)
    card_id: int = Field(foreign_key="cards.id", index=True)
    pack_name: str = Field(description="子包名称，如 Mewtwo")

    # 关系
    card: Optional[Card] = Relationship(back_populates="packs")
