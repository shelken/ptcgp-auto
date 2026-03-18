# -*- coding: utf-8 -*-
"""
高稀有度卡牌保存工具
"""

from ptcgp_auto_v2.config.constants import HIGH_RARITY_TARGETS


def save_high_rarity_cards(
    account_card_repo,
    account_id,
    rows: list[dict],
    account_name: str | None = None,
    notifier=None,
    notify_message: str | None = None,
    pack_name: str | None = None,
) -> None:
    """保存高稀有度卡牌，并统一在此触发通知。"""
    if not account_card_repo or not account_id:
        return

    should_notify = bool(notifier and account_name)
    for row in rows:
        card_id = row.get("card_id")
        rarity = row.get("rarity")
        if rarity not in HIGH_RARITY_TARGETS:
            continue
        if card_id:
            account_card_repo.increase_owned(
                account_id=account_id,
                card_id=card_id,
                amount=0,
                yolo_conf=float(row.get("confidence") or 0.0),
                hash_similarity=float(row.get("hash_similarity") or 0.0),
            )
        if not should_notify:
            continue

        card_name = row.get("card_name")
        card_data = row.get("card_data")
        set_code = row.get("set_code")
        card_number = row.get("card_number")
        if not card_id or not card_name or not set_code or card_number is None:
            continue
        notifier.notify_rare_card_data(
            account_id=account_id,
            account_name=account_name,
            card_id=int(card_id),
            card_name=str(card_name),
            card_data=card_data,
            set_code=str(set_code),
            card_number=int(card_number),
            rarity=str(rarity),
            pack_name=pack_name or "",
            image_url=None,
            message=notify_message,
        )
