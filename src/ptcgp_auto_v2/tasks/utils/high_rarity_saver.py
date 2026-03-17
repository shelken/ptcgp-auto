# -*- coding: utf-8 -*-
"""
高稀有度卡牌保存工具
"""

from ptcgp_auto_v2.config.constants import HIGH_RARITY_TARGETS


def save_high_rarity_cards(
    account_card_repo,
    account_id,
    rows: list[dict],
    account=None,
    notifier=None,
    notify_message: str | None = None,
    pack=None,
) -> None:
    """保存高稀有度卡牌，并统一在此触发通知。"""
    if not account_card_repo or not account_id:
        return

    for row in rows:
        card_id = row.get("card_id")
        rarity = row.get("rarity")
        if not card_id or rarity not in HIGH_RARITY_TARGETS:
            continue
        account_card_repo.increase_owned(
            account_id=account_id,
            card_id=card_id,
            amount=0,
            yolo_conf=float(row.get("confidence") or 0.0),
            hash_similarity=float(row.get("hash_similarity") or 0.0),
        )

    if not notifier or not account:
        return

    for row in rows:
        rarity = row.get("rarity")
        if rarity not in HIGH_RARITY_TARGETS:
            continue

        card_obj = row.get("card_obj")
        if not card_obj:
            continue
        notifier.notify_rare_card(
            account=account,
            card=card_obj,
            rarity=rarity,
            pack=pack,
            image_url=None,
            message=notify_message,
        )
