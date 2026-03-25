# -*- coding: utf-8 -*-
"""React API - 拥有卡牌路由。"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import Session

from ptcgp_auto_v2.db.engine import get_fastapi_session
from ptcgp_auto_v2.web.routers.react_api_common import json_response
from ptcgp_auto_v2.web.services.owned_card_service import (
    build_owned_card_exchange_accounts_context,
    build_owned_card_modal_context,
    build_owned_cards_list_context,
    build_owned_cards_progress_context,
)


router = APIRouter()


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
    context = build_owned_cards_list_context(
        session=session,
        page=page,
        page_size=page_size,
        account_id=account_id,
        rarity=rarity,
        card_type=card_type,
        set_code=set_code,
        pack_name=pack_name,
        element=element,
        sort_by=sort_by,
        ownership_scope=ownership_scope,
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
    context = build_owned_cards_progress_context(
        account_id=account_id,
        rarity=rarity,
        card_type=card_type,
        set_code=set_code,
        pack_name=pack_name,
        element=element,
        ownership_scope=ownership_scope,
    )
    return json_response(context)


@router.get("/owned-cards/{card_id}/detail")
async def get_owned_card_detail(
    card_id: int,
    ownership_state: str = Query(default="owned"),
    page_size: int = Query(default=10),
    session: Session = Depends(get_fastapi_session),
):
    """获取卡牌详情和交换账号数据。"""
    context = build_owned_card_modal_context(
        session=session,
        card_id=card_id,
        page_size=page_size,
        ownership_state=ownership_state,
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
    context = build_owned_card_exchange_accounts_context(
        session=session,
        card_id=card_id,
        page=page,
        page_size=page_size,
        q=q,
        sort_by=sort_by,
        sort_order=sort_order,
    )
    return json_response(context)
