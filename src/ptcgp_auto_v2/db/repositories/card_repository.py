# -*- coding: utf-8 -*-
import logging
from datetime import datetime
from typing import Any, List, Optional, cast

from sqlalchemy.orm import selectinload
from sqlmodel import Session, col, select

from ptcgp_auto_v2.db.engine import get_engine
from ptcgp_auto_v2.db.models import Card, CardPack, CardSet, Pack
from ptcgp_auto_v2.utils.card_naming import parse_card_number_from_filename

logger = logging.getLogger(__name__)


class CardRepository:
    """卡牌数据访问层"""

    def get_set_by_code(self, code: str) -> Optional[CardSet]:
        """根据代码获取系列"""
        with Session(get_engine()) as session:
            return session.get(CardSet, code)

    def upsert_set(self, card_set: CardSet) -> CardSet:
        """更新或创建系列"""
        with Session(get_engine()) as session:
            existing = session.get(CardSet, card_set.code)
            if existing:
                existing.name = card_set.name
                existing.release_date = card_set.release_date
                existing.total_cards = card_set.total_cards
                # 更新 label_data
                existing.label_data = card_set.label_data
                existing.updated_at = datetime.now()
                session.add(existing)
                session.commit()
                session.refresh(existing)
                return existing
            session.add(card_set)
            session.commit()
            session.refresh(card_set)
            return card_set

    def upsert_pack_safe(self, pack: Pack) -> Pack:
        """
        更新或创建卡包（安全模式）
        - 如果不存在: 创建
        - 如果存在: 仅更新 set_code 等基础字段，绝不覆盖人工维护的 label_data
        """
        with Session(get_engine()) as session:
            existing = session.get(Pack, pack.name)
            if existing:
                # 仅更新系统字段，保留人工数据
                existing.set_code = pack.set_code
                existing.updated_at = datetime.now()
                session.add(existing)
                session.commit()
                session.refresh(existing)
                return existing

            # 首次创建
            session.add(pack)
            session.commit()
            session.refresh(pack)
            return pack

    def get_all_packs(self) -> List[Pack]:
        """获取所有卡包"""
        with Session(get_engine()) as session:
            statement = select(Pack).order_by(Pack.set_code, Pack.name)
            return list(session.exec(statement).all())

    def get_pack_by_name(self, name: str) -> Optional[Pack]:
        """获取卡包详情"""
        with Session(get_engine()) as session:
             return session.get(Pack, name)

    def update_pack_label(self, name: str, label_data: str) -> bool:
        """更新卡包的多语言标签"""
        with Session(get_engine()) as session:
            pack = session.get(Pack, name)
            if not pack:
                return False
            pack.label_data = label_data
            pack.updated_at = datetime.now()
            session.add(pack)
            session.commit()
            return True

    def update_set_label(self, code: str, label_data: str) -> bool:
        """更新系列的多语言标签"""
        with Session(get_engine()) as session:
            card_set = session.get(CardSet, code)
            if not card_set:
                return False
            card_set.label_data = label_data
            card_set.updated_at = datetime.now()
            session.add(card_set)
            session.commit()
            return True

    def get_card_by_set_and_number(self, set_code: str, number: int) -> Optional[Card]:
        """根据系列和编号获取卡牌"""
        with Session(get_engine()) as session:
            statement = select(Card).where(
                Card.set_code == set_code, Card.number == number
            )
            return session.exec(statement).first()

    def get_card_by_template_name(self, set_code: str, template_name: str) -> Optional[Card]:
        """
        根据模板名称获取卡牌

        Args:
            set_code: 系列代码 (如 A1)
            template_name: 模板名称 (如 "001_Bulbasaur" 或 "025")

        Returns:
            Card对象或None
        """
        # 尝试提取开头的数字部分
        number = parse_card_number_from_filename(template_name)
        if number is not None:
            return self.get_card_by_set_and_number(set_code, number)

        logger.warning(f"Failed to parse card number from template: {template_name}")
        return None

    def upsert_card(self, card: Card) -> Card:
        """更新或创建卡牌"""
        with Session(get_engine()) as session:
            statement = select(Card).where(
                Card.set_code == card.set_code, Card.number == card.number
            )
            existing = session.exec(statement).first()
            if existing:
                existing.name = card.name
                existing.rarity = card.rarity
                existing.image_url = card.image_url
                # local_image_path 不覆盖，除非显式传入了新值
                if card.local_image_path:
                    existing.local_image_path = card.local_image_path
                existing.data = card.data

                # 新增字段更新
                existing.element = card.element
                existing.type = card.type
                existing.stage = card.stage
                existing.health = card.health
                existing.weakness = card.weakness
                existing.retreat_cost = card.retreat_cost

                existing.updated_at = datetime.now()
                session.add(existing)
                session.commit()
                session.refresh(existing)
                return existing
            session.add(card)
            session.commit()
            session.refresh(card)
            return card

    def clear_card_packs(self, card_id: int):
        """清除卡牌的卡包关联"""
        with Session(get_engine()) as session:
            statement = select(CardPack).where(CardPack.card_id == card_id)
            results = session.exec(statement).all()
            for item in results:
                session.delete(item)
            session.commit()

    def add_card_pack(self, card_id: int, pack_name: str):
        """添加卡牌与卡包的关联"""
        with Session(get_engine()) as session:
            # 检查是否已存在
            statement = select(CardPack).where(
                CardPack.card_id == card_id, CardPack.pack_name == pack_name
            )
            if session.exec(statement).first():
                return

            pack = CardPack(card_id=card_id, pack_name=pack_name)
            session.add(pack)
            session.commit()

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
        with Session(get_engine()) as session:
            # 获取系列信息
            card_set = session.get(CardSet, set_code)
            if not card_set:
                return {}

            # 获取该系列下所有卡牌关联的 pack_name
            # JOIN: CardSet -> Card -> CardPack
            statement = (
                select(CardPack.pack_name)
                .join(Card, col(CardPack.card_id) == col(Card.id))
                .where(Card.set_code == set_code)
                .distinct()
            )
            boosters = list(session.exec(statement).all())
            boosters.sort()

            return {
                set_code: {
                    "name": card_set.name,
                    "boosters": boosters,
                }
            }

    def get_all_sets(self) -> List[CardSet]:
        """获取所有系列"""
        with Session(get_engine()) as session:
            statement = select(CardSet).order_by(CardSet.code)
            return list(session.exec(statement).all())

    def get_cards_by_set(self, set_code: str) -> List[Card]:
        """获取系列下的所有卡牌"""
        with Session(get_engine()) as session:
            statement = (
                select(Card)
                .where(Card.set_code == set_code)
                .options(selectinload(cast(Any, Card.packs)))
            )
            return list(session.exec(statement).all())

    def get_cards_by_pack(self, pack_name: str, set_code: str) -> List[Card]:
        """获取指定子包下的所有卡牌"""
        with Session(get_engine()) as session:
            statement = (
                select(Card)
                .join(CardPack, col(Card.id) == col(CardPack.card_id))
                .where(Card.set_code == set_code, CardPack.pack_name == pack_name)
                .options(selectinload(cast(Any, Card.packs)))
            )
            return list(session.exec(statement).all())