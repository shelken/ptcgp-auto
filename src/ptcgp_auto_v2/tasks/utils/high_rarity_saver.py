# -*- coding: utf-8 -*-
"""
高稀有度卡牌保存工具
"""

from dataclasses import dataclass

from ptcgp_auto_v2.config.constants import HIGH_RARITY_TARGETS


@dataclass(slots=True, frozen=True)
class RareCardNotification:
    """稀有卡通知所需的纯数据。"""

    account_id: int
    account_name: str
    card_id: int
    card_name: str
    card_data: str | None
    set_code: str
    card_number: int
    rarity: str
    pack_name: str
    message: str | None


def save_high_rarity_cards(
    account_card_repo,
    account_id,
    rows: list[dict],
    account_name: str | None = None,
    notify_message: str | None = None,
    pack_name: str | None = None,
) -> list[RareCardNotification]:
    """保存高稀有度卡牌，返回待发送通知的数据。"""
    if not account_card_repo or not account_id:
        return []

    notifications: list[RareCardNotification] = []
    should_collect_notification = bool(account_name)
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
        if not should_collect_notification:
            continue

        card_name = row.get("card_name")
        card_data = row.get("card_data")
        set_code = row.get("set_code")
        card_number = row.get("card_number")
        if not card_id or not card_name or not set_code or card_number is None:
            continue
        notifications.append(
            RareCardNotification(
                account_id=account_id,
                account_name=account_name,
                card_id=int(card_id),
                card_name=str(card_name),
                card_data=card_data,
                set_code=str(set_code),
                card_number=int(card_number),
                rarity=str(rarity),
                pack_name=pack_name or "",
                message=notify_message,
            )
        )

    return notifications
