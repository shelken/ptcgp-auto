# -*- coding: utf-8 -*-
from dataclasses import dataclass
import logging
from datetime import datetime
from typing import Dict, Iterable, List, Optional

from sqlalchemy import and_, distinct, func, or_, tuple_
from sqlmodel import col, select

from ptcgp_auto_v2.db.models import AccountCard, Card, CardPack, CardSet, Pack
from .base import BaseRepository

logger = logging.getLogger(__name__)


@dataclass(slots=True, frozen=True)
class CardSetData:
    """系列纯数据对象。"""

    code: str
    name: str
    release_date: str | None
    total_cards: int
    label_data: str | None
    created_at: datetime
    updated_at: datetime


@dataclass(slots=True, frozen=True)
class PackData:
    """卡包纯数据对象。"""

    name: str
    set_code: str
    label_data: str | None
    sku_id: str | None
    image_url: str | None
    created_at: datetime
    updated_at: datetime


@dataclass(slots=True, frozen=True)
class CardData:
    """卡牌纯数据对象。"""

    id: int
    set_code: str
    number: int
    name: str
    rarity: str
    image_url: str | None
    element: str | None
    type: str | None
    stage: str | None
    health: int | None
    weakness: str | None
    retreat_cost: int | None
    local_image_path: str | None
    perceptual_hash: str | None
    data: str | None
    created_at: datetime
    updated_at: datetime


class CardRepository(BaseRepository):
    """卡牌数据访问层"""

    def get_set_by_code(self, code: str) -> Optional[CardSetData]:
        """根据代码获取系列。"""
        card_set = self.session.get(CardSet, code)
        if card_set is None:
            return None
        return self._to_data(CardSetData, card_set)

    def get_by_id(self, card_id: int) -> Optional[CardData]:
        """根据主键获取卡牌。"""
        card = self.session.get(Card, card_id)
        if card is None:
            return None
        return self._to_data(CardData, card)

    def upsert_set(self, card_set: CardSet) -> None:
        """更新或创建系列。"""
        existing = self.session.get(CardSet, card_set.code)
        if existing:
            existing.name = card_set.name
            existing.release_date = card_set.release_date
            existing.total_cards = card_set.total_cards
            existing.label_data = card_set.label_data
            existing.updated_at = datetime.now()
            self.session.add(existing)
            self._finish_write(existing)
            return
        self.session.add(card_set)
        self._finish_write(card_set)

    def upsert_pack_safe(self, pack: Pack) -> None:
        """
        更新或创建卡包（安全模式）
        - 如果不存在: 创建
        - 如果存在: 仅更新 set_code 等基础字段，绝不覆盖人工维护的 label_data
        """
        existing = self.session.get(Pack, pack.name)
        if existing:
            existing.set_code = pack.set_code
            # 变更原因：补充同步需要填充新资产映射，但不能覆盖人工 label_data。
            if pack.sku_id:
                existing.sku_id = pack.sku_id
            if pack.image_url:
                existing.image_url = pack.image_url
            existing.updated_at = datetime.now()
            self.session.add(existing)
            self._finish_write(existing)
            return
        self.session.add(pack)
        self._finish_write(pack)

    def get_all_packs(self) -> List[PackData]:
        """获取所有卡包。"""
        statement = select(Pack).order_by(Pack.set_code, Pack.name)
        return [self._to_data(PackData, pack) for pack in self.session.exec(statement).all()]

    def get_pack_names_by_set(
        self, set_code: str, exclude_promo: bool = False
    ) -> List[str]:
        """按系列获取子包名称列表。

        Args:
            set_code: 系列代码
            exclude_promo: 是否排除 PROMO 前缀的子包
        """
        statement = select(Pack.name).where(Pack.set_code == set_code)
        if exclude_promo:
            statement = statement.where(func.upper(col(Pack.name)).not_like("PROMO%"))
        statement = statement.order_by(Pack.name)
        return list(self.session.exec(statement).all())

    def get_packs_by_set_prefixes(
        self, prefixes: list[str], exclude_set_codes: list[str]
    ) -> List[PackData]:
        """按系列前缀获取子包列表并排除指定系列。"""
        normalized_prefixes = [item for item in prefixes if item]
        # 注意：不要转换大小写，系列代码是大小写敏感的（如 A4b 不是 A4B）
        exclude_set = {code for code in exclude_set_codes if code}
        statement = select(Pack)
        if normalized_prefixes:
            conditions = [
                col(Pack.set_code).like(f"{item}%") for item in normalized_prefixes
            ]
            statement = statement.where(or_(*conditions))
        if exclude_set:
            statement = statement.where(col(Pack.set_code).not_in(exclude_set))
        statement = statement.order_by(Pack.set_code, Pack.name)
        return [self._to_data(PackData, pack) for pack in self.session.exec(statement).all()]

    def get_pack_target_rarity_progress(
        self,
        pack_names: list[str],
        target_rarities: list[str],
    ) -> dict[str, dict[str, int]]:
        """按子包统计目标稀有度全账号并集进度。"""
        if not pack_names or not target_rarities:
            return {}

        statement = (
            select(
                CardPack.pack_name,
                func.count(distinct(col(Card.id))).label("total_target"),
                func.count(distinct(col(AccountCard.card_id))).label("owned_target"),
            )
            .select_from(CardPack)
            .join(Card, col(Card.id) == col(CardPack.card_id))
            .outerjoin(
                AccountCard,
                and_(
                    col(AccountCard.card_id) == col(Card.id),
                    col(AccountCard.count) > 0,
                ),
            )
            .where(
                col(CardPack.pack_name).in_(pack_names),
                col(Card.rarity).in_(target_rarities),
            )
            .group_by(col(CardPack.pack_name))
        )
        rows = self.session.exec(statement).all()
        return {
            pack_name: {
                "total_target": int(total_target or 0),
                "owned_target": int(owned_target or 0),
            }
            for pack_name, total_target, owned_target in rows
        }

    def get_pack_by_name(self, name: str) -> Optional[PackData]:
        """获取卡包详情。"""
        pack = self.session.get(Pack, name)
        if pack is None:
            return None
        return self._to_data(PackData, pack)

    def update_pack_label(self, name: str, label_data: str) -> bool:
        """更新卡包的多语言标签"""
        pack = self.session.get(Pack, name)
        if not pack:
            return False
        pack.label_data = label_data
        pack.updated_at = datetime.now()
        self.session.add(pack)
        self._finish_write(pack)
        return True

    def update_set_label(self, code: str, label_data: str) -> bool:
        """更新系列的多语言标签"""
        card_set = self.session.get(CardSet, code)
        if not card_set:
            return False
        card_set.label_data = label_data
        card_set.updated_at = datetime.now()
        self.session.add(card_set)
        self._finish_write(card_set)
        return True

    def get_card_by_set_and_number(
        self, set_code: str, number: int
    ) -> Optional[CardData]:
        """根据系列和编号获取卡牌。"""
        statement = select(Card).where(Card.set_code == set_code, Card.number == number)
        card = self.session.exec(statement).first()
        if card is None:
            return None
        return self._to_data(CardData, card)

    def get_cards_by_set_and_numbers(
        self, keys: Iterable[tuple[str, int]]
    ) -> dict[tuple[str, int], CardData]:
        """按系列和编号批量获取卡牌。"""
        normalized_keys = sorted(set(keys))
        if not normalized_keys:
            return {}
        statement = select(Card).where(
            tuple_(Card.set_code, Card.number).in_(normalized_keys)
        )
        return {
            (card.set_code, card.number): self._to_data(CardData, card)
            for card in self.session.exec(statement).all()
        }

    def upsert_card(self, card: Card) -> int | None:
        """更新或创建卡牌。"""
        statement = select(Card).where(
            Card.set_code == card.set_code, Card.number == card.number
        )
        existing = self.session.exec(statement).first()
        if existing:
            existing.name = card.name
            existing.rarity = card.rarity
            existing.image_url = card.image_url
            if card.local_image_path:
                existing.local_image_path = card.local_image_path
            existing.data = card.data
            existing.element = card.element
            existing.type = card.type
            existing.stage = card.stage
            existing.health = card.health
            existing.weakness = card.weakness
            existing.retreat_cost = card.retreat_cost
            existing.updated_at = datetime.now()
            self.session.add(existing)
            self._finish_write(existing)
            return int(existing.id) if existing.id is not None else None
        self.session.add(card)
        self._finish_write(card)
        return int(card.id) if card.id is not None else None

    def add_card_pack(self, card_id: int, pack_name: str):
        """添加卡牌与卡包的关联"""
        statement = select(CardPack).where(
            CardPack.card_id == card_id, CardPack.pack_name == pack_name
        )
        if self.session.exec(statement).first():
            return
        self.session.add(CardPack(card_id=card_id, pack_name=pack_name))
        self._finish_write()

    def get_card_pack_names(self, card_id: int) -> list[str]:
        """获取指定卡牌当前关联的卡包名称列表。"""
        statement = (
            select(CardPack.pack_name)
            .where(CardPack.card_id == card_id)
            .order_by(CardPack.pack_name)
        )
        return list(self.session.exec(statement).all())

    def get_card_pack_names_map(
        self, card_ids: Iterable[int]
    ) -> dict[int, list[str]]:
        """按卡牌 ID 批量获取当前关联的卡包名称列表。"""
        normalized_ids = sorted(set(card_ids))
        if not normalized_ids:
            return {}
        statement = (
            select(CardPack.card_id, CardPack.pack_name)
            .where(col(CardPack.card_id).in_(normalized_ids))
            .order_by(CardPack.card_id, CardPack.pack_name)
        )
        result: dict[int, list[str]] = {card_id: [] for card_id in normalized_ids}
        for card_id, pack_name in self.session.exec(statement).all():
            result[int(card_id)].append(str(pack_name))
        return result

    def get_packs_by_set(self, set_code: str) -> dict:
        """
        获取指定系列的子包结构（用于生成兼容的 packs.json）
        Returns:
            {
                "set_code": {
                    "name": "SetName",
                    "boosters": ["Pack1", "Pack2"]
                }
            }
        """
        card_set = self.get_set_by_code(set_code)
        if not card_set:
            return {}
        # 变更原因：pack 归属来自 packs 表，card_packs 只表示获取来源，不能反推系列子包列表。
        statement = select(Pack.name).where(Pack.set_code == set_code).order_by(Pack.name)
        boosters = list(self.session.exec(statement).all())
        return {set_code: {"name": card_set.name, "boosters": boosters}}

    def get_all_sets(self) -> List[CardSetData]:
        """获取所有系列。"""
        statement = select(CardSet).order_by(CardSet.code)
        return [self._to_data(CardSetData, card_set) for card_set in self.session.exec(statement).all()]

    def get_metadata_counts(self) -> dict[str, int]:
        """获取 metadata 基础统计。"""
        sets_count = int(self.session.exec(select(func.count()).select_from(CardSet)).one() or 0)
        packs_count = int(self.session.exec(select(func.count()).select_from(Pack)).one() or 0)
        cards_count = int(
            self.session.exec(
                select(func.count())
                .select_from(Card)
                .join(CardSet, col(Card.set_code) == col(CardSet.code))
            ).one()
            or 0
        )
        return {"sets": sets_count, "packs": packs_count, "cards": cards_count}

    def get_set_labels_map(self, set_codes: list[str]) -> dict[str, str | None]:
        """按系列代码批量获取 label_data 映射。"""
        if not set_codes:
            return {}
        statement = select(CardSet.code, CardSet.label_data).where(
            col(CardSet.code).in_(set_codes)
        )
        return {str(code): label_data for code, label_data in self.session.exec(statement).all()}

    def get_pack_labels_map(self, pack_names: list[str]) -> dict[str, str | None]:
        """按子包名称批量获取 label_data 映射。"""
        if not pack_names:
            return {}
        statement = select(Pack.name, Pack.label_data).where(col(Pack.name).in_(pack_names))
        return {
            str(pack_name): label_data
            for pack_name, label_data in self.session.exec(statement).all()
        }

    def get_cards_by_set(self, set_code: str) -> List[CardData]:
        """获取系列下的所有卡牌。"""
        statement = select(Card).where(Card.set_code == set_code).order_by(Card.number)
        return [self._to_data(CardData, card) for card in self.session.exec(statement).all()]

    def get_cards_by_pack(self, pack_name: str, set_code: str) -> List[CardData]:
        """获取指定子包下的所有卡牌。"""
        statement = (
            select(Card)
            .join(CardPack, col(Card.id) == col(CardPack.card_id))
            .where(Card.set_code == set_code, CardPack.pack_name == pack_name)
            .order_by(Card.number)
        )
        return [self._to_data(CardData, card) for card in self.session.exec(statement).all()]

    def get_cards_without_hash(self, set_code: str) -> List[CardData]:
        """获取某系列缺少感知哈希的卡牌。"""
        statement = (
            select(Card)
            .where(Card.set_code == set_code, Card.perceptual_hash.is_(None))
            .order_by(Card.number)
        )
        return [self._to_data(CardData, card) for card in self.session.exec(statement).all()]

    def update_card_hash(self, card_id: int, hash_value: str) -> bool:
        """更新卡牌感知哈希值"""
        card = self.session.get(Card, card_id)
        if not card:
            return False
        card.perceptual_hash = hash_value
        card.updated_at = datetime.now()
        self.session.add(card)
        self._finish_write(card)
        return True

    def get_cards_with_hash_by_set(self, set_code: str) -> Dict[int, str]:
        """获取某系列所有有hash的卡牌 {number: hash}"""
        statement = (
            select(Card.number, Card.perceptual_hash)
            .where(Card.set_code == set_code, Card.perceptual_hash.is_not(None))
            .order_by(Card.number)
        )
        return {
            int(number): str(hash_value)
            for number, hash_value in self.session.exec(statement).all()
            if hash_value is not None
        }
