# -*- coding: utf-8 -*-
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional, cast

from sqlalchemy import and_, distinct, func, or_
from sqlalchemy.orm import selectinload
from sqlmodel import Session, col, select

from ptcgp_auto_v2.db.engine import get_engine
from ptcgp_auto_v2.db.models import AccountCard, Card, CardPack, CardSet, Pack
from ptcgp_auto_v2.utils.card_naming import parse_card_number_from_filename

logger = logging.getLogger(__name__)


class CardRepository:
    """卡牌数据访问层"""

    def get_set_by_code(self, code: str) -> Optional[CardSet]:
        """根据代码获取系列"""
        with Session(get_engine()) as session:
            return session.get(CardSet, code)

    def get_by_id(self, card_id: int) -> Optional[Card]:
        """根据主键获取卡牌。"""
        with Session(get_engine()) as session:
            return session.get(Card, card_id)

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

    def get_pack_names_by_set(
        self, set_code: str, exclude_promo: bool = False
    ) -> List[str]:
        """按系列获取子包名称列表。

        Args:
            set_code: 系列代码
            exclude_promo: 是否排除 PROMO 前缀的子包
        """
        with Session(get_engine()) as session:
            statement = select(Pack.name).where(Pack.set_code == set_code)

            if exclude_promo:
                # 过滤 PROMO 前缀（不区分大小写）
                statement = statement.where(
                    func.upper(col(Pack.name)).not_like("PROMO%")
                )

            statement = statement.order_by(Pack.name)
            return list(session.exec(statement).all())

    def get_packs_by_set_prefixes(
        self, prefixes: list[str], exclude_set_codes: list[str]
    ) -> List[Pack]:
        """按系列前缀获取子包列表并排除指定系列。"""
        normalized_prefixes = [item for item in prefixes if item]
        # 注意：不要转换大小写，系列代码是大小写敏感的（如 A4b 不是 A4B）
        exclude_set = {code for code in exclude_set_codes if code}
        with Session(get_engine()) as session:
            statement = select(Pack)
            if normalized_prefixes:
                conditions = [
                    col(Pack.set_code).like(f"{item}%") for item in normalized_prefixes
                ]
                statement = statement.where(or_(*conditions))
            if exclude_set:
                statement = statement.where(col(Pack.set_code).not_in(exclude_set))
            statement = statement.order_by(Pack.set_code, Pack.name)
            return list(session.exec(statement).all())

    def get_pack_target_rarity_progress(
        self,
        pack_names: list[str],
        target_rarities: list[str],
    ) -> dict[str, dict[str, int]]:
        """按子包统计目标稀有度全账号并集进度。"""
        if not pack_names or not target_rarities:
            return {}

        with Session(get_engine()) as session:
            statement = (
                select(
                    CardPack.pack_name,
                    func.count(distinct(col(Card.id))).label("total_target"),
                    func.count(distinct(col(AccountCard.card_id))).label(
                        "owned_target"
                    ),
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
            rows = session.exec(statement).all()
            return {
                pack_name: {
                    "total_target": int(total_target or 0),
                    "owned_target": int(owned_target or 0),
                }
                for pack_name, total_target, owned_target in rows
            }

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

    def get_card_by_template_name(
        self, set_code: str, template_name: str
    ) -> Optional[Card]:
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

    def remove_card_pack(self, card_id: int, pack_name: str):
        """移除卡牌与指定卡包的关联。"""
        with Session(get_engine()) as session:
            statement = select(CardPack).where(
                CardPack.card_id == card_id,
                CardPack.pack_name == pack_name,
            )
            row = session.exec(statement).first()
            if not row:
                return
            session.delete(row)
            session.commit()

    def get_card_pack_names(self, card_id: int) -> list[str]:
        """获取指定卡牌当前关联的卡包名称列表。"""
        with Session(get_engine()) as session:
            statement = (
                select(CardPack.pack_name)
                .where(CardPack.card_id == card_id)
                .order_by(CardPack.pack_name)
            )
            return list(session.exec(statement).all())

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

    def get_latest_set_with_pack(self) -> Optional[tuple[CardSet, Pack]]:
        """
        获取最新发布的系列及其一个随机子包

        Returns:
            (CardSet, Pack) 元组，如果没有则返回 None
            排除 promo/PROMO 开头的系列（不区分大小写）
        """
        import random
        from sqlalchemy import func

        with Session(get_engine()) as session:
            # 1. 获取最新发布的系列（排除 promo 开头的，不区分大小写）
            statement = (
                select(CardSet)
                .where(func.upper(col(CardSet.code)).not_like("PROMO%"))
                .order_by(CardSet.release_date.desc())
            )
            latest_set = session.exec(statement).first()

            if not latest_set:
                logger.warning("未找到非 promo 的系列")
                return None

            # 2. 获取该系列下的所有子包
            statement = select(Pack).where(Pack.set_code == latest_set.code)
            packs = list(session.exec(statement).all())

            if not packs:
                logger.warning(f"系列 {latest_set.code} 没有关联的子包")
                return None

            # 3. 随机选择一个子包
            selected_pack = random.choice(packs)
            return latest_set, selected_pack

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

    def get_cards_without_hash(self, set_code: str) -> List[Card]:
        """获取某系列缺少感知哈希的卡牌"""
        with Session(get_engine()) as session:
            statement = select(Card).where(
                Card.set_code == set_code, Card.perceptual_hash.is_(None)
            )
            return list(session.exec(statement).all())

    def update_card_hash(self, card_id: int, hash_value: str) -> bool:
        """更新卡牌感知哈希值"""
        with Session(get_engine()) as session:
            card = session.get(Card, card_id)
            if not card:
                return False
            card.perceptual_hash = hash_value
            card.updated_at = datetime.now()
            session.add(card)
            session.commit()
            return True

    def get_cards_with_hash_by_set(self, set_code: str) -> Dict[int, str]:
        """获取某系列所有有hash的卡牌 {number: hash}"""
        with Session(get_engine()) as session:
            statement = (
                select(Card)
                .where(Card.set_code == set_code, Card.perceptual_hash.is_not(None))
                .order_by(Card.number)
            )
            cards = session.exec(statement).all()
            return {card.number: card.perceptual_hash for card in cards}

    def get_card_pack_names_batch(
        self, card_ids: list[int], exclude_promo: bool = False
    ) -> dict[int, list[str]]:
        """批量获取卡牌关联的子包名称。

        Args:
            card_ids: 卡牌ID列表
            exclude_promo: 是否排除 PROMO 前缀的子包

        Returns:
            {card_id: [pack_name, ...]} 映射
        """
        if not card_ids:
            return {}

        with Session(get_engine()) as session:
            # 构建基础查询
            statement = select(CardPack.card_id, CardPack.pack_name).where(
                col(CardPack.card_id).in_(card_ids)
            )

            if exclude_promo:
                # 过滤 PROMO 前缀（不区分大小写）
                statement = statement.where(
                    func.upper(col(CardPack.pack_name)).not_like("PROMO%")
                )

            results = session.exec(statement).all()

            # 聚合结果
            mapping: dict[int, list[str]] = {}
            for card_id, pack_name in results:
                if card_id not in mapping:
                    mapping[card_id] = []
                mapping[card_id].append(pack_name)

            return mapping
