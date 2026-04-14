# -*- coding: utf-8 -*-
"""React API - 拥有卡牌路由。"""

from __future__ import annotations

from collections.abc import Mapping

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import Session

from ptcgp_auto_v2.db.engine import get_fastapi_session
from ptcgp_auto_v2.web.routers.react_api_common import (
    json_response,
    normalize_pagination_params,
)
from ptcgp_auto_v2.web.services.owned_card_service import (
    build_owned_card_exchange_accounts_context,
    build_owned_card_modal_context,
    build_owned_cards_list_context,
    build_owned_cards_progress_context,
)
from ptcgp_auto_v2.web.utils.filter_utils import (
    normalize_choice,
    normalize_page_size,
    normalize_query_text,
    normalize_sort_order,
)
from ptcgp_auto_v2.web.utils.form_utils import parse_optional_int


router = APIRouter()

OWNERSHIP_SCOPES = {"owned", "missing", "all"}
OWNED_CARD_SORT_FIELDS = {"acquired", "rarity", "count"}
EXCHANGE_ACCOUNT_SORT_FIELDS = {
    "account_id",
    "friend_id",
    "nickname",
    "count",
    "exchange_points",
}


def _normalize_query_list(raw: object) -> list[str]:
    """统一归一化多选查询参数。"""
    if not isinstance(raw, list):
        return []
    values: list[str] = []
    for item in raw:
        text = str(item).strip()
        if text:
            values.append(text)
    return values


def _build_owned_cards_common_filter_query_params(
    raw: Mapping[str, object],
) -> dict[str, object]:
    """统一解析拥有卡牌主列表与统计共享筛选状态。"""
    account_id = normalize_query_text(str(raw.get("account_id") or ""))
    return {
        "account_id": account_id or None,
        "rarity": _normalize_query_list(raw.get("rarity")),
        "card_type": _normalize_query_list(raw.get("card_type")),
        "set_code": _normalize_query_list(raw.get("set_code")),
        "pack_name": _normalize_query_list(raw.get("pack_name")),
        "element": _normalize_query_list(raw.get("element")),
        "ownership_scope": normalize_choice(
            str(raw.get("ownership_scope") or ""),
            allowed=OWNERSHIP_SCOPES,
            default="owned",
        ),
    }


def _build_owned_cards_list_query_params(raw: Mapping[str, object]) -> dict[str, object]:
    """统一解析拥有卡牌主列表查询参数。"""
    page = parse_optional_int(raw.get("page"))
    page_size = parse_optional_int(raw.get("page_size"))
    normalized_page, normalized_page_size = normalize_pagination_params(
        page=page if page is not None else 0,
        page_size=page_size if page_size is not None else 60,
    )
    sort_by = str(raw.get("sort_by") or "acquired")
    normalized_sort_by = (
        sort_by if sort_by in OWNED_CARD_SORT_FIELDS else "acquired"
    )
    return {
        **_build_owned_cards_common_filter_query_params(raw),
        "page": normalized_page,
        "page_size": normalized_page_size,
        "sort_by": normalized_sort_by,
    }


def _build_owned_cards_stats_query_params(raw: Mapping[str, object]) -> dict[str, object]:
    """统一解析拥有卡牌统计查询参数。"""
    return _build_owned_cards_common_filter_query_params(raw)


def _build_owned_card_detail_query_params(raw: Mapping[str, object]) -> dict[str, object]:
    """统一解析拥有卡牌详情弹窗查询参数。"""
    page_size = parse_optional_int(raw.get("page_size"))
    ownership_scope = str(
        raw.get("ownership_scope")
        or raw.get("ownership_state")
        or "owned"
    )
    return {
        "ownership_scope": normalize_choice(
            ownership_scope,
            allowed=OWNERSHIP_SCOPES,
            default="owned",
        ),
        "page_size": normalize_page_size(
            page_size if page_size is not None else 10,
            max_size=50,
        ),
    }


def _build_owned_card_exchange_accounts_query_params(
    raw: Mapping[str, object],
) -> dict[str, object]:
    """统一解析拥有卡牌详情账号表查询参数。"""
    page = parse_optional_int(raw.get("page"))
    page_size = parse_optional_int(raw.get("page_size"))
    normalized_page, normalized_page_size = normalize_pagination_params(
        page=page if page is not None else 0,
        page_size=page_size if page_size is not None else 10,
        max_size=50,
    )
    sort_by = str(raw.get("sort_by") or "account_id")
    normalized_sort_by = (
        sort_by if sort_by in EXCHANGE_ACCOUNT_SORT_FIELDS else "account_id"
    )
    return {
        "page": normalized_page,
        "page_size": normalized_page_size,
        "q": normalize_query_text(str(raw.get("q") or "")),
        "sort_by": normalized_sort_by,
        "sort_order": normalize_sort_order(str(raw.get("sort_order") or "asc")),
    }


@router.get("/owned-cards")
async def get_owned_cards(
    page: int = Query(default=0),
    page_size: int = Query(default=60),
    account_id: str | None = Query(default=None),
    rarity: list[str] = Query(default=[]),
    card_type: list[str] = Query(default=[]),
    set_code: list[str] = Query(default=[]),
    pack_name: list[str] = Query(default=[]),
    element: list[str] = Query(default=[]),
    sort_by: str = Query(default="acquired"),
    ownership_scope: str = Query(default="owned"),
    session: Session = Depends(get_fastapi_session),
):
    """获取拥有卡牌列表数据。"""
    query_params = _build_owned_cards_list_query_params(
        {
            "page": page,
            "page_size": page_size,
            "account_id": account_id,
            "rarity": rarity,
            "card_type": card_type,
            "set_code": set_code,
            "pack_name": pack_name,
            "element": element,
            "sort_by": sort_by,
            "ownership_scope": ownership_scope,
        }
    )
    context = build_owned_cards_list_context(
        session=session,
        **query_params,
    )
    return json_response(context)


@router.get("/owned-cards/stats")
async def get_owned_cards_stats(
    account_id: str | None = Query(default=None),
    rarity: list[str] = Query(default=[]),
    card_type: list[str] = Query(default=[]),
    set_code: list[str] = Query(default=[]),
    pack_name: list[str] = Query(default=[]),
    element: list[str] = Query(default=[]),
    ownership_scope: str = Query(default="owned"),
):
    """获取拥有卡牌统计。"""
    query_params = _build_owned_cards_stats_query_params(
        {
            "account_id": account_id,
            "rarity": rarity,
            "card_type": card_type,
            "set_code": set_code,
            "pack_name": pack_name,
            "element": element,
            "ownership_scope": ownership_scope,
        }
    )
    context = build_owned_cards_progress_context(
        **query_params,
    )
    return json_response(context)


@router.get("/owned-cards/{card_id}/detail")
async def get_owned_card_detail(
    card_id: int,
    ownership_scope: str | None = Query(default=None),
    ownership_state: str | None = Query(default=None),
    page_size: int = Query(default=10),
    session: Session = Depends(get_fastapi_session),
):
    """获取卡牌详情和交换账号数据。"""
    query_params = _build_owned_card_detail_query_params(
        {
            "ownership_scope": ownership_scope,
            "ownership_state": ownership_state,
            "page_size": page_size,
        }
    )
    context = build_owned_card_modal_context(
        session=session,
        card_id=card_id,
        **query_params,
    )
    if context is None:
        raise HTTPException(status_code=404, detail="card_not_found")
    return json_response(context)


@router.get("/owned-cards/{card_id}/exchange-accounts")
async def get_owned_card_exchange_accounts(
    card_id: int,
    page: int = Query(default=0),
    page_size: int = Query(default=10),
    q: str = Query(default=""),
    sort_by: str = Query(default="account_id"),
    sort_order: str = Query(default="asc"),
    session: Session = Depends(get_fastapi_session),
):
    """获取卡牌交换账号分页数据。"""
    query_params = _build_owned_card_exchange_accounts_query_params(
        {
            "page": page,
            "page_size": page_size,
            "q": q,
            "sort_by": sort_by,
            "sort_order": sort_order,
        }
    )
    context = build_owned_card_exchange_accounts_context(
        session=session,
        card_id=card_id,
        **query_params,
    )
    return json_response(context)
