from typing import Any

from sqlmodel import Session

from ptcgp_auto_v2.db.models.card import Card
from ptcgp_auto_v2.db.repositories import (
    AccountCardRepository,
    ExchangeCardRequestRepository,
)
from ptcgp_auto_v2.services import ExchangeCardService
from ptcgp_auto_v2.web.queries.owned_card_queries import build_owned_cards_next_page_url
from ptcgp_auto_v2.web.utils.form_utils import parse_optional_int
from ptcgp_auto_v2.web.utils.i18n import get_current_i18n


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
) -> dict[str, Any]:
    """获取已拥有卡牌列表视图数据。"""
    current_lang, t = get_current_i18n()
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
    session: Session, card_id: int
) -> dict[str, Any] | None:
    """构建已拥有卡牌详情弹窗所需数据。"""
    current_lang, t = get_current_i18n()
    card = session.get(Card, card_id)
    if not card:
        return None

    table_context = build_owned_card_exchange_accounts_context(
        session=session,
        card_id=card_id,
        page=0,
        page_size=10,
        q="",
        sort_by="account_id",
        sort_order="asc",
    )
    exchange_blocked = card.rarity in ExchangeCardService.NON_EXCHANGEABLE_RARITIES
    return {
        "card": card,
        "accounts": table_context["accounts"],
        "exchange_blocked": exchange_blocked,
        "total_accounts": table_context["total_items"],
        "total_count": table_context["total_count"],
        "exchange_table": table_context,
        "t": t,
        "current_lang": current_lang,
    }


def _normalize_exchange_sort(sort_by: str, sort_order: str) -> tuple[str, str]:
    """标准化交换账号排序参数（白名单）。"""
    allowed_sort = {"account_id", "friend_id", "nickname", "count"}
    normalized_sort_by = sort_by if sort_by in allowed_sort else "account_id"
    normalized_sort_order = "desc" if sort_order == "desc" else "asc"
    return normalized_sort_by, normalized_sort_order


def _match_exchange_query(item: dict[str, Any], query: str) -> bool:
    """判断账号行是否命中搜索词。"""
    if not query:
        return True
    keyword = query.lower()
    account_id = str(item.get("account_id") or "").lower()
    friend_id = str(item.get("friend_id") or "").lower()
    nickname = str(item.get("nickname") or "").lower()
    return keyword in account_id or keyword in friend_id or keyword in nickname


def build_owned_card_exchange_accounts_context(
    session: Session,
    card_id: int,
    page: int = 0,
    page_size: int = 10,
    q: str = "",
    sort_by: str = "account_id",
    sort_order: str = "asc",
) -> dict[str, Any]:
    """构建已拥有卡牌弹窗中的交换账号分页表格上下文。"""
    current_lang, t = get_current_i18n()

    normalized_page = max(page, 0)
    normalized_page_size = min(max(page_size, 1), 50)
    normalized_sort_by, normalized_sort_order = _normalize_exchange_sort(
        sort_by, sort_order
    )

    card = session.get(Card, card_id)
    if not card:
        return {
            "card": None,
            "accounts": [],
            "total_items": 0,
            "total_count": 0,
            "page": normalized_page,
            "page_size": normalized_page_size,
            "has_prev": False,
            "has_next": False,
            "q": q,
            "sort_by": normalized_sort_by,
            "sort_order": normalized_sort_order,
            "t": t,
            "current_lang": current_lang,
        }

    repo = AccountCardRepository()
    exchange_repo = ExchangeCardRequestRepository()
    data = repo.get_owned_card_accounts(card_id)

    filtered = []
    for item in data["accounts"]:
        if not _match_exchange_query(item, q):
            continue
        account_id = item.get("account_id")
        item["has_active_request"] = bool(
            account_id and exchange_repo.has_active_request(account_id)
        )
        filtered.append(item)

    reverse = normalized_sort_order == "desc"
    if normalized_sort_by == "friend_id":
        filtered.sort(key=lambda x: str(x.get("friend_id") or ""), reverse=reverse)
    elif normalized_sort_by == "nickname":
        filtered.sort(key=lambda x: str(x.get("nickname") or ""), reverse=reverse)
    elif normalized_sort_by == "count":
        filtered.sort(key=lambda x: int(x.get("count") or 0), reverse=reverse)
    else:
        filtered.sort(key=lambda x: int(x.get("account_id") or 0), reverse=reverse)

    total_items = len(filtered)
    start = normalized_page * normalized_page_size
    end = start + normalized_page_size
    paged_items = filtered[start:end]

    return {
        "card": card,
        "accounts": paged_items,
        "exchange_blocked": card.rarity
        in ExchangeCardService.NON_EXCHANGEABLE_RARITIES,
        "total_items": total_items,
        "total_count": int(data.get("total_count") or 0),
        "page": normalized_page,
        "page_size": normalized_page_size,
        "has_prev": normalized_page > 0,
        "has_next": end < total_items,
        "q": q,
        "sort_by": normalized_sort_by,
        "sort_order": normalized_sort_order,
        "t": t,
        "current_lang": current_lang,
    }
