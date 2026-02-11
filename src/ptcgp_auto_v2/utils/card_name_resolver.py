# -*- coding: utf-8 -*-
"""
卡牌名称解析工具
"""

from typing import Optional


def resolve_card_name(
    card_repo, set_code: Optional[str], card_number: int
) -> Optional[str]:
    """按系列与卡号解析名称，无法解析时返回 None。"""
    if not card_repo:
        return None
    if not set_code:
        return None
    card = card_repo.get_card_by_set_and_number(set_code, card_number)
    if not card:
        return None
    return getattr(card, "name", None)
