# -*- coding: utf-8 -*-
"""开包识别结果映射工具。"""

from __future__ import annotations

from typing import TYPE_CHECKING

from ptcgp_auto_v2.db.repositories.card_repository import CardData
from ptcgp_auto_v2.infra.yolo_card_recognizer import DetectedCard

if TYPE_CHECKING:
    from ptcgp_auto_v2.db.repositories import CardRepository


def map_detected_cards(
    card_repo: "CardRepository | None",
    cards: list[DetectedCard],
    fixed_set_code: str | None = None,
) -> list[dict]:
    """统一构建识别卡牌结构，供记录保存复用。"""
    card_cache: dict[tuple[str, int], CardData | None] = {}
    rows: list[dict] = []
    for index, card in enumerate(cards):
        set_code = fixed_set_code or card.set_code
        card_data = None
        if card_repo is not None and set_code:
            cache_key = (set_code, card.card_number)
            if cache_key not in card_cache:
                card_cache[cache_key] = card_repo.get_card_by_set_and_number(
                    set_code, card.card_number
                )
            card_data = card_cache[cache_key]

        rows.append(
            {
                "card_id": card_data.id if card_data else None,
                "card_name": (
                    card_data.name if card_data else f"Card #{card.card_number}"
                ),
                "card_data": card_data.data if card_data else None,
                "rarity": card_data.rarity if card_data else "Unknown",
                "set_code": set_code,
                "card_number": card.card_number,
                "center_x": float(card.center[0]),
                "center_y": float(card.center[1]),
                "is_new": False,
                "position": index + 1,
                "confidence": float(card.confidence),
                "hash_similarity": float(card.similarity),
            }
        )
    return rows
