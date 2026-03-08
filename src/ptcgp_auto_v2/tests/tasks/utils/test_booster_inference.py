# -*- coding: utf-8 -*-
"""
子包推断工具测试

测试两阶段子包推断逻辑：模板优先 + 卡牌兜底。
"""

from unittest.mock import MagicMock

from ptcgp_auto_v2.tasks.utils.booster_inference import infer_pack_by_cards


def create_mock_card(card_id: int, set_code: str, pack_names: list[str]):
    """创建模拟的 Card 对象"""
    card = MagicMock()
    card.id = card_id
    card.set_code = set_code
    # 模拟 packs 关系
    card.packs = []
    for pack_name in pack_names:
        pack_mock = MagicMock()
        pack_mock.pack_name = pack_name
        card.packs.append(pack_mock)
    return card


class TestCardFallbackInference:
    """卡牌反推推断测试"""

    def test_card_fallback_majority_set_single_pack(self):
        """测试系列占比超过一半且只有一个子包时直接判定"""
        # A1 有 2 张，A2 有 1 张，A1 超过 50%
        cards = [
            create_mock_card(1, "A1", ["Mewtwo"]),
            create_mock_card(2, "A1", ["Mewtwo"]),
            create_mock_card(3, "A2", ["Charizard"]),
        ]

        result = infer_pack_by_cards(cards)

        assert result is not None
        assert result["set_code"] == "A1"
        assert result["booster_name"] == "Mewtwo"
        assert result["source"] == "cards"

    def test_card_fallback_majority_set_multi_pack_unique_evidence(self):
        """测试多子包时根据唯一归属卡牌判定"""
        cards = [
            # 10 和 12 只出现在 Mewtwo，11 同时出现在两者
            create_mock_card(10, "A2", ["Mewtwo"]),
            create_mock_card(11, "A2", ["Mewtwo", "Charizard"]),
            create_mock_card(12, "A2", ["Mewtwo"]),
        ]

        result = infer_pack_by_cards(cards)

        assert result is not None
        assert result["set_code"] == "A2"
        assert result["booster_name"] == "Mewtwo"
        assert result["source"] == "cards"

    def test_card_fallback_ambiguous_pack_name_none(self):
        """测试无法唯一确定子包时返回 pack_name=None"""
        # A2 有 2 张，A3 有 1 张，A2 超过 50%
        # 但所有卡牌都在多个子包中出现，无法唯一确定
        cards = [
            create_mock_card(20, "A2", ["Mewtwo", "Charizard"]),
            create_mock_card(21, "A2", ["Mewtwo", "Charizard"]),
            create_mock_card(22, "A3", ["Pikachu"]),
        ]

        result = infer_pack_by_cards(cards)

        assert result is not None
        assert result["set_code"] == "A2"  # 系列可以确定
        assert result["booster_name"] is None  # 子包无法确定
        assert result["source"] == "cards"

    def test_card_fallback_no_majority_set(self):
        """测试没有明显多数系列时返回 None"""
        # A1 和 A2 各 1 张，没有超过 50%
        cards = [
            create_mock_card(1, "A1", ["Mewtwo"]),
            create_mock_card(2, "A2", ["Charizard"]),
        ]

        result = infer_pack_by_cards(cards)

        assert result is None

    def test_card_fallback_empty_cards(self):
        """测试空卡牌列表返回 None"""
        result = infer_pack_by_cards([])
        assert result is None

    def test_card_fallback_missing_packs(self):
        """测试卡牌没有子包信息时忽略该卡牌"""
        # 1 有子包，999 没有子包
        cards = [
            create_mock_card(1, "A1", ["Mewtwo"]),
            create_mock_card(999, "A1", []),  # 无子包
        ]

        result = infer_pack_by_cards(cards)

        assert result is not None
        assert result["set_code"] == "A1"
        assert result["booster_name"] == "Mewtwo"

    def test_card_fallback_excludes_promo_packs(self):
        """测试排除 PROMO 子包"""
        cards = [
            # 同时属于普通子包和 PROMO 子包，应该只考虑普通子包
            create_mock_card(1, "A1", ["Mewtwo", "PROMO-A1"]),
            create_mock_card(2, "A1", ["Mewtwo", "PROMO-A1"]),
        ]

        result = infer_pack_by_cards(cards)

        assert result is not None
        assert result["set_code"] == "A1"
        assert result["booster_name"] == "Mewtwo"  # 不是 PROMO-A1

    def test_card_fallback_all_promo_packs_ignored(self):
        """测试当所有子包都是 PROMO 时，卡牌被忽略"""
        cards = [
            create_mock_card(1, "A1", ["PROMO-A1"]),
            create_mock_card(2, "A1", ["PROMO-A1"]),
        ]

        result = infer_pack_by_cards(cards)

        # 所有卡牌的子包都被排除，没有有效卡牌
        assert result is None

    def test_card_fallback_tie_returns_none_for_booster(self):
        """测试证据数平局时返回 booster_name=None"""
        # Charizard 和 Mewtwo 都有 1 个唯一证据
        cards = [
            create_mock_card(1, "A2", ["Mewtwo"]),
            create_mock_card(2, "A2", ["Charizard"]),
        ]

        result = infer_pack_by_cards(cards)

        assert result is not None
        assert result["set_code"] == "A2"
        assert result["booster_name"] is None  # 平局，无法确定
        assert result["source"] == "cards"

    def test_card_fallback_filters_invalid_cards(self):
        """测试过滤无效卡牌（无 id 或无 set_code）"""
        valid_card = create_mock_card(1, "A1", ["Mewtwo"])
        no_id_card = create_mock_card(None, "A1", ["Mewtwo"])  # type: ignore
        no_set_card = create_mock_card(2, None, ["Mewtwo"])  # type: ignore

        cards = [valid_card, no_id_card, no_set_card]

        result = infer_pack_by_cards(cards)

        assert result is not None
        assert result["set_code"] == "A1"
        assert result["booster_name"] == "Mewtwo"
