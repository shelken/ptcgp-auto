# -*- coding: utf-8 -*-
"""
子包推断工具测试

测试两阶段子包推断逻辑：模板优先 + 卡牌兜底。
"""

from ptcgp_auto_v2.tasks.utils.booster_inference import (
    infer_pack_by_templates,
    infer_pack_by_cards,
)


class TestTemplateInference:
    """模板识别推断测试"""

    def test_template_inference_selects_best_score_pack(self):
        """测试选择最高分且超过阈值的子包"""
        candidates = [
            {
                "pack_code": "A2",
                "booster_name": "Mewtwo",
                "template": "packs_auto/Mewtwo",
            },
            {
                "pack_code": "A2",
                "booster_name": "Charizard",
                "template": "packs_auto/Charizard",
            },
        ]

        def matcher(name: str):
            # 模拟匹配器返回置信度
            score = 0.72 if name.endswith("Mewtwo") else 0.61
            return {"score": score, "box": (100, 100, 200, 200)}

        result = infer_pack_by_templates(
            candidate_templates=candidates, matcher_fn=matcher, threshold=0.65
        )

        assert result is not None
        assert result["pack_code"] == "A2"
        assert result["booster_name"] == "Mewtwo"
        assert result["source"] == "template"
        assert result["score"] == 0.72

    def test_template_inference_returns_none_when_below_threshold(self):
        """测试所有候选都低于阈值时返回 None"""
        candidates = [
            {
                "pack_code": "A2",
                "booster_name": "Mewtwo",
                "template": "packs_auto/Mewtwo",
            },
        ]

        def matcher(name: str):
            return {"score": 0.60, "box": (100, 100, 200, 200)}  # 低于阈值 0.65

        result = infer_pack_by_templates(
            candidate_templates=candidates, matcher_fn=matcher, threshold=0.65
        )

        assert result is None

    def test_template_inference_returns_none_for_empty_candidates(self):
        """测试空候选列表返回 None"""
        result = infer_pack_by_templates(
            candidate_templates=[], matcher_fn=lambda x: {"score": 0.9}, threshold=0.65
        )
        assert result is None


class TestCardFallbackInference:
    """卡牌反推推断测试"""

    def test_card_fallback_majority_set_single_pack(self):
        """测试系列占比超过一半且只有一个子包时直接判定"""
        detected_rows = [
            {"set_code": "A1", "card_id": 1},
            {"set_code": "A1", "card_id": 2},
            {"set_code": "A2", "card_id": 3},
        ]
        pack_names_by_set = {"A1": ["Mewtwo"], "A2": ["Charizard", "Pikachu"]}
        card_pack_mapping = {1: ["Mewtwo"], 2: ["Mewtwo"], 3: ["Charizard"]}

        result = infer_pack_by_cards(
            detected_rows=detected_rows,
            pack_names_by_set=pack_names_by_set,
            card_pack_mapping=card_pack_mapping,
        )

        assert result is not None
        assert result["pack_code"] == "A1"
        assert result["booster_name"] == "Mewtwo"
        assert result["source"] == "cards"

    def test_card_fallback_majority_set_multi_pack_unique_evidence(self):
        """测试多子包时根据唯一归属卡牌判定"""
        detected_rows = [
            {"set_code": "A2", "card_id": 10},
            {"set_code": "A2", "card_id": 11},
            {"set_code": "A2", "card_id": 12},
        ]
        pack_names_by_set = {"A2": ["Mewtwo", "Charizard"]}
        # 10 和 12 只出现在 Mewtwo，11 同时出现在两者
        card_pack_mapping = {
            10: ["Mewtwo"],
            11: ["Mewtwo", "Charizard"],
            12: ["Mewtwo"],
        }

        result = infer_pack_by_cards(
            detected_rows=detected_rows,
            pack_names_by_set=pack_names_by_set,
            card_pack_mapping=card_pack_mapping,
        )

        assert result is not None
        assert result["pack_code"] == "A2"
        assert result["booster_name"] == "Mewtwo"
        assert result["source"] == "cards"

    def test_card_fallback_ambiguous_pack_name_none(self):
        """测试无法唯一确定子包时返回 pack_name=None"""
        detected_rows = [
            {"set_code": "A2", "card_id": 20},
            {"set_code": "A2", "card_id": 21},
            {"set_code": "A3", "card_id": 22},
        ]
        pack_names_by_set = {"A2": ["Mewtwo", "Charizard"]}
        # 所有卡牌都在多个子包中出现，无法唯一确定
        card_pack_mapping = {20: ["Mewtwo", "Charizard"], 21: ["Mewtwo", "Charizard"]}

        result = infer_pack_by_cards(
            detected_rows=detected_rows,
            pack_names_by_set=pack_names_by_set,
            card_pack_mapping=card_pack_mapping,
        )

        assert result is not None
        assert result["pack_code"] == "A2"  # 系列可以确定
        assert result["booster_name"] is None  # 子包无法确定
        assert result["source"] == "cards"

    def test_card_fallback_no_majority_set(self):
        """测试没有明显多数系列时返回 None"""
        detected_rows = [
            {"set_code": "A1", "card_id": 1},
            {"set_code": "A2", "card_id": 2},
        ]
        pack_names_by_set = {"A1": ["Mewtwo"], "A2": ["Charizard"]}
        card_pack_mapping = {1: ["Mewtwo"], 2: ["Charizard"]}

        result = infer_pack_by_cards(
            detected_rows=detected_rows,
            pack_names_by_set=pack_names_by_set,
            card_pack_mapping=card_pack_mapping,
        )

        assert result is None

    def test_card_fallback_empty_detected_rows(self):
        """测试空卡牌列表返回 None"""
        result = infer_pack_by_cards(
            detected_rows=[],
            pack_names_by_set={"A1": ["Mewtwo"]},
            card_pack_mapping={},
        )
        assert result is None

    def test_card_fallback_missing_card_in_mapping(self):
        """测试卡牌不在映射中时忽略该卡牌"""
        detected_rows = [
            {"set_code": "A1", "card_id": 1},
            {"set_code": "A1", "card_id": 999},  # 不在映射中
        ]
        pack_names_by_set = {"A1": ["Mewtwo"]}
        card_pack_mapping = {1: ["Mewtwo"]}  # 999 不在映射中

        result = infer_pack_by_cards(
            detected_rows=detected_rows,
            pack_names_by_set=pack_names_by_set,
            card_pack_mapping=card_pack_mapping,
        )

        assert result is not None
        assert result["pack_code"] == "A1"
        assert result["booster_name"] == "Mewtwo"
