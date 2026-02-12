from typing import Any

from sqlmodel import Session

from ptcgp_auto_v2.db.models.card import Card
from ptcgp_auto_v2.db.repositories import AccountCardRepository
from ptcgp_auto_v2.services import ExchangeCardService
from ptcgp_auto_v2.web.queries.owned_card_queries import build_owned_cards_next_page_url
from ptcgp_auto_v2.web.utils.form_utils import parse_optional_int
from ptcgp_auto_v2.web.utils.i18n import get_translations, normalize_lang


def list_owned_cards(
    page: int,
    page_size: int,
    account_id: str | None,
    rarity: list[str],
    card_type: list[str],
    set_code: list[str],
    pack_name: list[str],
    element: list[str],
    sort_by: str,
    lang: str,
) -> dict[str, Any]:
    """获取已拥有卡牌列表视图数据。"""
    current_lang = normalize_lang(lang)
    t = get_translations(current_lang)
    repo = AccountCardRepository()
    account_id_value = parse_optional_int(account_id)
    items = repo.list_owned_cards(
        page=page,
        page_size=page_size,
        account_id=account_id_value,
        rarities=rarity,
        card_types=card_type,
        set_codes=set_code,
        pack_names=pack_name,
        elements=element,
        sort_by=sort_by,
    )

    if not items and page > 0:
        return {"stop": True}

    next_page_url = build_owned_cards_next_page_url(
        page,
        current_lang,
        sort_by,
        account_id_value,
        rarity,
        card_type,
        set_code,
        pack_name,
        element,
    )

    return {
        "stop": False,
        "items": items,
        "next_page_url": next_page_url,
        "page": page,
        "t": t,
        "current_lang": current_lang,
    }


def build_owned_card_modal_context(
    session: Session, card_id: int, lang: str
) -> dict[str, Any] | None:
    """构建已拥有卡牌详情弹窗所需数据。"""
    current_lang = normalize_lang(lang)
    t = get_translations(current_lang)
    card = session.get(Card, card_id)
    if not card:
        return None

    repo = AccountCardRepository()
    data = repo.get_owned_card_accounts(card_id)
    exchange_accounts = [
        item for item in data["accounts"] if int(item.get("count", 0) or 0) > 0
    ]
    exchange_blocked = card.rarity in ExchangeCardService.NON_EXCHANGEABLE_RARITIES
    return {
        "card": card,
        "accounts": data["accounts"],
        "exchange_accounts": exchange_accounts,
        "exchange_blocked": exchange_blocked,
        "total_accounts": data["total_accounts"],
        "total_count": data["total_count"],
        "t": t,
        "current_lang": current_lang,
    }
