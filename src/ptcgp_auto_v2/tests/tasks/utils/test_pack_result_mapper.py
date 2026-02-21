# -*- coding: utf-8 -*-
"""开包结果映射工具测试。"""

from types import SimpleNamespace

from ptcgp_auto_v2.infra.yolo_card_recognizer import DetectedCard
from ptcgp_auto_v2.tasks.utils.pack_result_mapper import (
    map_detected_cards,
)


class _FakeCardRepo:
    def __init__(self, card_map):
        self._card_map = card_map

    def get_card_by_set_and_number(self, set_code, card_number):
        return self._card_map.get((set_code, card_number))


def test_map_detected_cards_builds_unified_structure():
    repo = _FakeCardRepo(
        {
            ("A1", 1): SimpleNamespace(id=101, rarity="SR"),
        }
    )
    detected = [
        DetectedCard(
            set_code="A1",
            card_number=1,
            confidence=0.9,
            similarity=0.8,
            bbox=(0, 0, 1, 1),
            center=(0.0, 0.0),
        ),
        DetectedCard(
            set_code="A1",
            card_number=2,
            confidence=0.7,
            similarity=0.6,
            bbox=(0, 0, 1, 1),
            center=(0.0, 0.0),
        ),
        DetectedCard(
            set_code="",
            card_number=3,
            confidence=0.6,
            similarity=0.5,
            bbox=(0, 0, 1, 1),
            center=(0.0, 0.0),
        ),
    ]

    rows = map_detected_cards(detected, repo)

    assert len(rows) == 3
    assert rows[0]["card_obj"] is not None and rows[0]["card_obj"].id == 101
    assert rows[0]["card_id"] == 101
    assert rows[0]["card_name"] == "Card #1"
    assert rows[1]["card_obj"] is None
    assert rows[1]["card_id"] is None
    assert rows[2]["card_obj"] is None
