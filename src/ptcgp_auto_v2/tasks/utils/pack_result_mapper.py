# -*- coding: utf-8 -*-
"""开包识别结果映射工具。"""

from __future__ import annotations

from typing import TYPE_CHECKING, Optional

from ptcgp_auto_v2.infra.yolo_card_recognizer import DetectedCard

if TYPE_CHECKING:
    from ptcgp_auto_v2.db.models import Card
    from ptcgp_auto_v2.db.repositories import CardRepository


def map_detected_cards(
    cards: list[DetectedCard],
    card_repo: "CardRepository | None",
    fixed_set_code: str | None = None,
) -> list[dict]:
    """统一构建识别卡牌结构，供记录保存与高稀有度保存复用。"""
    rows: list[dict] = []
    for index, card in enumerate(cards):
        set_code = fixed_set_code or card.set_code
        card_obj: Optional["Card"] = None
        if card_repo is not None and set_code:
            # 使用 eager loading 加载 packs 关系，供后续子包推断使用
            card_obj = card_repo.get_card_by_set_and_number(
                set_code, card.card_number, load_packs=True
            )

        rows.append(
            {
                "card_obj": card_obj,
                "card_name": (
                    card_obj.name
                    if card_obj and getattr(card_obj, "name", None)
                    else f"Card #{card.card_number}"
                ),
                "rarity": card_obj.rarity if card_obj else "Unknown",
                "card_id": card_obj.id if card_obj else None,
                "is_new": False,
                "position": index + 1,
                "confidence": float(card.confidence),
                "hash_similarity": float(card.similarity),
            }
        )
    return rows
