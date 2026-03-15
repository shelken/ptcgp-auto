# -*- coding: utf-8 -*-
"""开包识别结果映射工具。"""

from __future__ import annotations

from typing import TYPE_CHECKING, Optional

from ptcgp_auto_v2.infra.yolo_card_recognizer import DetectedCard

if TYPE_CHECKING:
    from ptcgp_auto_v2.db.models import Card
    from ptcgp_auto_v2.db.repositories import CardRepository


class PackResultMapper:
    """开包识别结果映射器，内部统一管理卡牌查询缓存。"""

    def __init__(self, card_repo: "CardRepository | None"):
        self._card_repo = card_repo
        self._card_cache: dict[tuple[str, int], "Card | None"] = {}

    def _resolve_card_obj(
        self, set_code: str | None, card_number: int
    ) -> Optional["Card"]:
        if self._card_repo is None or not set_code:
            return None

        cache_key = (set_code, card_number)
        if cache_key in self._card_cache:
            return self._card_cache[cache_key]

        # 使用 eager loading 加载 packs 关系，供后续子包推断使用
        try:
            card_obj = self._card_repo.get_card_by_set_and_number(
                set_code, card_number, load_packs=True
            )
        except TypeError:
            card_obj = self._card_repo.get_card_by_set_and_number(set_code, card_number)
        self._card_cache[cache_key] = card_obj
        return card_obj

    def map_detected_cards(
        self,
        cards: list[DetectedCard],
        fixed_set_code: str | None = None,
    ) -> list[dict]:
        """统一构建识别卡牌结构，供记录保存与高稀有度保存复用。"""
        rows: list[dict] = []
        for index, card in enumerate(cards):
            set_code = fixed_set_code or card.set_code
            card_obj = self._resolve_card_obj(set_code, card.card_number)

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


def map_detected_cards(
    cards: list[DetectedCard],
    card_repo: "CardRepository | None",
    fixed_set_code: str | None = None,
) -> list[dict]:
    """兼容旧调用方式的便捷函数。"""
    return PackResultMapper(card_repo).map_detected_cards(
        cards=cards,
        fixed_set_code=fixed_set_code,
    )
