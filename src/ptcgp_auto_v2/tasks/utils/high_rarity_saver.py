# -*- coding: utf-8 -*-
"""
高稀有度卡牌保存工具
"""

from ptcgp_auto_v2.config.constants import HIGH_RARITY_TARGETS


def save_high_rarity_cards(account_card_repo, account_id, cards: list[dict]) -> None:
    if not account_card_repo or not account_id:
        return
    for item in cards:
        card_id = item.get("card_id")
        rarity = item.get("rarity")
        if not card_id or rarity not in HIGH_RARITY_TARGETS:
            continue
        account_card_repo.upsert(
            account_id=account_id,
            card_id=card_id,
            count=1,
            yolo_conf=float(item.get("confidence") or 0.0),
            hash_similarity=float(item.get("hash_similarity") or 0.0),
        )
