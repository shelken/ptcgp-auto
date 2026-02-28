# -*- coding: utf-8 -*-
"""
CardRepository 测试

测试子包推断相关的仓储查询能力。
"""

import pytest
from sqlmodel import Session

from ptcgp_auto_v2.db.models import Card, CardPack, CardSet, Pack
from ptcgp_auto_v2.db.repositories.card_repository import CardRepository


class TestBoosterInferenceQueries:
    """子包推断相关查询测试"""

    def test_get_pack_names_by_set_excludes_promo_when_requested(self, session):
        """测试 exclude_promo=True 时过滤 PROMO 前缀子包"""
        repo = CardRepository()

        # 准备数据：创建系列、子包和卡牌关联
        card_set = CardSet(code="A1", name="Test Set A1")
        session.add(card_set)

        pack1 = Pack(name="Mewtwo", set_code="A1")
        pack2 = Pack(name="PROMO-A1-001", set_code="A1")
        session.add_all([pack1, pack2])

        session.commit()

        # 测试 exclude_promo=False（默认）
        packs_all = repo.get_pack_names_by_set("A1", exclude_promo=False)
        assert len(packs_all) == 2

        # 测试 exclude_promo=True
        packs_filtered = repo.get_pack_names_by_set("A1", exclude_promo=True)
        assert len(packs_filtered) == 1
        assert all(not name.upper().startswith("PROMO") for name in packs_filtered)
        assert "Mewtwo" in packs_filtered
        assert "PROMO-A1-001" not in packs_filtered

    def test_get_card_pack_names_batch_returns_mapping(self, session):
        """测试批量获取卡牌子包关系"""
        repo = CardRepository()

        # 准备数据
        card_set = CardSet(code="A1", name="Test Set")
        session.add(card_set)

        pack1 = Pack(name="Mewtwo", set_code="A1")
        pack2 = Pack(name="Charizard", set_code="A1")
        session.add_all([pack1, pack2])

        card1 = Card(
            set_code="A1", number=1, name="Card 1", rarity="C", image_url="url1"
        )
        card2 = Card(
            set_code="A1", number=2, name="Card 2", rarity="C", image_url="url2"
        )
        session.add_all([card1, card2])
        session.flush()

        # 建立关联
        cp1 = CardPack(card_id=card1.id, pack_name="Mewtwo")
        cp2 = CardPack(card_id=card2.id, pack_name="Mewtwo")
        cp3 = CardPack(card_id=card2.id, pack_name="Charizard")
        session.add_all([cp1, cp2, cp3])
        session.commit()

        # 测试批量查询
        mapping = repo.get_card_pack_names_batch([card1.id, card2.id])

        assert isinstance(mapping, dict)
        assert card1.id in mapping
        assert card2.id in mapping
        assert isinstance(mapping[card1.id], list)
        assert "Mewtwo" in mapping[card1.id]
        assert set(mapping[card2.id]) == {"Mewtwo", "Charizard"}

    def test_get_card_pack_names_batch_excludes_promo_when_requested(self, session):
        """测试批量查询时过滤 PROMO 子包"""
        repo = CardRepository()

        # 准备数据
        card_set = CardSet(code="A1", name="Test Set")
        session.add(card_set)

        pack1 = Pack(name="Mewtwo", set_code="A1")
        pack2 = Pack(name="PROMO-A1-001", set_code="A1")
        session.add_all([pack1, pack2])

        card = Card(
            set_code="A1", number=1, name="Card 1", rarity="C", image_url="url1"
        )
        session.add(card)
        session.flush()

        # 建立关联（同时关联普通子包和 PROMO 子包）
        cp1 = CardPack(card_id=card.id, pack_name="Mewtwo")
        cp2 = CardPack(card_id=card.id, pack_name="PROMO-A1-001")
        session.add_all([cp1, cp2])
        session.commit()

        # 测试 exclude_promo=True
        mapping = repo.get_card_pack_names_batch([card.id], exclude_promo=True)
        assert "Mewtwo" in mapping[card.id]
        assert "PROMO-A1-001" not in mapping[card.id]
