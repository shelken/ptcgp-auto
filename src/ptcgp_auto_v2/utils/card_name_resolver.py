# -*- coding: utf-8 -*-
"""
卡牌名称解析工具
"""

from typing import Optional


def resolve_card_name(card_repo, set_code: str, card_number: int) -> Optional[str]:
    if not card_repo:
        return None
    card = card_repo.get_card_by_set_and_number(set_code, card_number)
    if not card:
        return None
    return getattr(card, "name", None)
