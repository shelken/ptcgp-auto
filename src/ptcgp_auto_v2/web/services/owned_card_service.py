from typing import Any

from sqlmodel import Session

from ptcgp_auto_v2.db.models.card import Card
from ptcgp_auto_v2.db.engine import session_scope
from ptcgp_auto_v2.db.repositories import (
    AccountCardRepository,
    ExchangeCardRequestRepository,
)
from ptcgp_auto_v2.services import ExchangeCardService
from ptcgp_auto_v2.web.utils.filter_utils import (
    normalize_choice,
    normalize_page,
    normalize_page_size,
    normalize_sort_order,
)
from ptcgp_auto_v2.web.utils.i18n import get_current_i18n, resolve_card_name_from_data

OWNERSHIP_SCOPES = {"owned", "missing", "all"}
EXCHANGE_ACCOUNT_SORT_FIELDS = {
    "account_id",
    "friend_id",
    "nickname",
    "count",
    "exchange_points",
}


def _normalize_ownership_scope(value: str | None) -> str:
    """归一化卡牌拥有状态筛选值。"""
    return normalize_choice(value, allowed=OWNERSHIP_SCOPES, default="owned")


def _build_owned_card_filters(
    *,
    account_id: str | None,
    rarity: list[str] | None,
    card_type: list[str] | None,
    set_code: list[str] | None,
    pack_name: list[str] | None,
    element: list[str] | None,
    ownership_scope: str,
) -> dict[str, Any]:
    """构建仓储查询参数。"""
    return {
        "account_query": account_id,
        "rarities": rarity or [],
        "card_types": card_type or [],
        "set_codes": set_code or [],
        "pack_names": pack_name or [],
        "elements": element or [],
        "ownership_scope": ownership_scope,
    }


def _attach_card_display_names(items: list[dict[str, Any]]) -> None:
    """为卡牌列表补齐当前语言展示名。"""
    for item in items:
        card = item.get("card") if isinstance(item, dict) else None
        if isinstance(card, Card):
            item["card_display_name"] = resolve_card_name_from_data(
                card.data,
                fallback=card.name,
            )


def _normalize_exchange_account_sort(
    sort_by: str,
    sort_order: str,
) -> tuple[str, str]:
    """归一化交换账号表格排序参数。"""
    normalized_sort_by = (
        sort_by if sort_by in EXCHANGE_ACCOUNT_SORT_FIELDS else "account_id"
    )
    return normalized_sort_by, normalize_sort_order(sort_order)


def _matches_exchange_account_keyword(item: dict[str, Any], keyword: str) -> bool:
    """判断账号行是否命中关键词。"""
    if not keyword:
        return True
    account_id = str(item.get("account_id") or "").lower()
    friend_id = str(item.get("friend_id") or "").lower()
    nickname = str(item.get("nickname") or "").lower()
    return keyword in account_id or keyword in friend_id or keyword in nickname


def _sort_exchange_account_rows(
    rows: list[dict[str, Any]],
    *,
    sort_by: str,
    sort_order: str,
) -> None:
    """按目标字段排序交换账号行。"""
    reverse = sort_order == "desc"
    if sort_by == "friend_id":
        rows.sort(key=lambda x: str(x.get("friend_id") or ""), reverse=reverse)
        return
    if sort_by == "nickname":
        rows.sort(key=lambda x: str(x.get("nickname") or ""), reverse=reverse)
        return
    if sort_by == "count":
        rows.sort(key=lambda x: int(x.get("count") or 0), reverse=reverse)
        return
    if sort_by == "exchange_points":
        rows.sort(key=lambda x: int(x.get("exchange_points") or -1), reverse=reverse)
        return
    rows.sort(key=lambda x: int(x.get("account_id") or 0), reverse=reverse)


def build_owned_cards_list_context(
    *,
    session: Session,
    page: int = 0,
    page_size: int = 10,
    account_id: str | None = None,
    rarity: list[str] | None = None,
    card_type: list[str] | None = None,
    set_code: list[str] | None = None,
    pack_name: list[str] | None = None,
    element: list[str] | None = None,
    sort_by: str = "acquired",
    ownership_scope: str = "owned",
) -> dict[str, Any]:
    """构建已拥有卡牌列表视图上下文（统一列表协议）。

    返回字段:
        - items: 卡牌列表
        - page: 当前页码
        - page_size: 每页大小
        - has_prev: 是否有上一页
        - has_next: 是否有下一页
        - total: 总数量
    """
    normalized_page = normalize_page(page)
    normalized_page_size = normalize_page_size(page_size)
    normalized_scope = _normalize_ownership_scope(ownership_scope)
    filters = _build_owned_card_filters(
        account_id=account_id,
        rarity=rarity,
        card_type=card_type,
        set_code=set_code,
        pack_name=pack_name,
        element=element,
        ownership_scope=normalized_scope,
    )

    repo = AccountCardRepository(session)
    items = repo.list_owned_cards(
        page=normalized_page,
        page_size=normalized_page_size,
        **filters,
        sort_by=sort_by,
    )

    has_next = len(items) > normalized_page_size
    items = items[:normalized_page_size]
    has_prev = normalized_page > 0

    total = repo.count_cards_by_scope(
        **filters,
    )
    _attach_card_display_names(items)

    return {
        "items": items,
        "page": normalized_page,
        "page_size": normalized_page_size,
        "has_prev": has_prev,
        "has_next": has_next,
        "total": total,
        "ownership_scope": normalized_scope,
    }


def build_owned_cards_progress_context(
    *,
    account_id: str | None = None,
    rarity: list[str] | None = None,
    card_type: list[str] | None = None,
    set_code: list[str] | None = None,
    pack_name: list[str] | None = None,
    element: list[str] | None = None,
    ownership_scope: str = "owned",
) -> dict[str, Any]:
    """构建拥有卡牌页顶部统计上下文。"""
    normalized_scope = _normalize_ownership_scope(ownership_scope)
    filters = _build_owned_card_filters(
        account_id=account_id,
        rarity=rarity,
        card_type=card_type,
        set_code=set_code,
        pack_name=pack_name,
        element=element,
        ownership_scope=normalized_scope,
    )
    with session_scope() as session:
        repo = AccountCardRepository(session)
        filtered_cards_count = repo.count_cards_by_scope(**filters)
        rarity_progress = repo.get_high_rarity_progress()
        return {
            "filtered_cards_count": filtered_cards_count,
            "rarity_progress": rarity_progress,
            "ownership_scope": normalized_scope,
        }


def build_owned_card_modal_context(
    session: Session,
    card_id: int,
    page_size: int = 10,
    ownership_state: str = "owned",
) -> dict[str, Any] | None:
    """构建已拥有卡牌详情弹窗所需数据。"""
    card = session.get(Card, card_id)
    if not card:
        return None

    table_context = build_owned_card_exchange_accounts_context(
        session=session,
        card_id=card_id,
        page=0,
        page_size=page_size,
        q="",
        sort_by="account_id",
        sort_order="asc",
    )
    exchange_blocked = not ExchangeCardService.is_exchangeable(card.rarity)
    return {
        "card": card,
        "card_display_name": resolve_card_name_from_data(
            card.data,
            fallback=card.name,
        ),
        "ownership_state": (
            _normalize_ownership_scope(ownership_state)
        ),
        "exchange_blocked": exchange_blocked,
        "total_accounts": table_context["total_items"],
        "total_count": table_context["total_count"],
        "exchange_table": table_context,
    }


def _build_exchange_action(card: Card, item: dict[str, Any]) -> dict[str, Any]:
    """统一计算交换按钮状态，避免模板散落业务判断。"""
    _, t = get_current_i18n()
    required_points = ExchangeCardService.get_required_exchange_points(card.rarity) or 0
    current_points = int(item.get("exchange_points") or 0)

    disabled_reason_text: str | None = None
    disabled_reason_key: str | None = None
    if not ExchangeCardService.is_exchangeable(card.rarity):
        disabled_reason_key = "blocked_rarity"
        disabled_reason_text = (
            t.get("exchange_entry_blocked_rarity") or "该稀有度不可交换"
        )
    elif int(item.get("count") or 0) <= 0:
        disabled_reason_key = "missing_owned_card"
        disabled_reason_text = (
            t.get("exchange_entry_missing_owned_card") or "该账号没有可交换的此卡"
        )
    elif bool(item.get("has_active_request")):
        disabled_reason_key = "has_active_request"
        disabled_reason_text = (
            t.get("exchange_has_active_request")
            or "该账号有进行中的交换请求，无法创建新请求"
        )
    elif current_points < required_points:
        disabled_reason_key = "insufficient_exchange_points"
        disabled_reason_text = (
            t.get("exchange_entry_insufficient_points") or "该账号交换点数不足"
        )

    return {
        # 统一由服务层产出按钮状态，模板只消费渲染结果。
        "enabled": disabled_reason_text is None,
        "reason_key": disabled_reason_key,
        "reason_text": disabled_reason_text,
        "button_text": t.get("exchange_entry_action") or "交换卡牌",
        "tooltip": disabled_reason_text,
    }


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
    normalized_page = normalize_page(page)
    normalized_page_size = normalize_page_size(page_size, max_size=50)
    normalized_sort_by, normalized_sort_order = _normalize_exchange_account_sort(
        sort_by,
        sort_order,
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
        }

    repo = AccountCardRepository(session)
    exchange_repo = ExchangeCardRequestRepository(session)
    data = repo.get_owned_card_accounts(card_id)
    exchangeable = ExchangeCardService.is_exchangeable(card.rarity)

    keyword = q.lower()
    filtered: list[dict[str, Any]] = []
    for item in data["accounts"]:
        if not _matches_exchange_account_keyword(item, keyword):
            continue
        row = dict(item)
        account_id = row.get("account_id")
        row["has_active_request"] = bool(
            account_id and exchange_repo.has_active_request(account_id)
        )
        row["exchange_action"] = _build_exchange_action(card, row)
        filtered.append(row)

    _sort_exchange_account_rows(
        filtered,
        sort_by=normalized_sort_by,
        sort_order=normalized_sort_order,
    )

    total_items = len(filtered)
    start = normalized_page * normalized_page_size
    end = start + normalized_page_size
    paged_items = filtered[start:end]

    return {
        "card": card,
        "accounts": paged_items,
        "exchange_blocked": not exchangeable,
        "total_items": total_items,
        "total_count": int(data.get("total_count") or 0),
        "page": normalized_page,
        "page_size": normalized_page_size,
        "has_prev": normalized_page > 0,
        "has_next": end < total_items,
        "q": q,
        "sort_by": normalized_sort_by,
        "sort_order": normalized_sort_order,
    }
