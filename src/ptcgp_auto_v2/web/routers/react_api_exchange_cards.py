# -*- coding: utf-8 -*-
"""React API - 交换卡牌路由。"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Request
from sqlmodel import Session

from ptcgp_auto_v2.db.engine import get_fastapi_session
from ptcgp_auto_v2.web.services.exchange_card_service import (
    build_exchange_card_context,
    cancel_exchange_request,
    create_exchange_request_with_task,
)
from ptcgp_auto_v2.web.routers.react_api_common import json_response
from ptcgp_auto_v2.web.utils.form_utils import parse_optional_int
from ptcgp_auto_v2.web.utils.i18n import get_current_i18n

router = APIRouter()


@router.post("/exchange-cards/requests")
async def create_exchange_request(request: Request):
    """创建交换请求。"""
    body = await request.json()
    from_account_id = parse_optional_int(body.get("from_account_id"))
    to_account_id = parse_optional_int(body.get("to_account_id"))
    target_card_id = parse_optional_int(body.get("target_card_id"))
    to_friend_id = str(body.get("to_friend_id") or "").strip()
    target_card_rarity = str(body.get("target_card_rarity") or "")

    ok = False
    if from_account_id and target_card_id and to_friend_id:
        ok = create_exchange_request_with_task(
            from_account_id=from_account_id,
            to_account_id=to_account_id,
            to_friend_id=to_friend_id,
            target_card_id=target_card_id,
            target_card_rarity=target_card_rarity,
        )

    _, t = get_current_i18n()
    return json_response(
        {
            "ok": ok,
            "message": (
                t.get("msg_exchange_request_created")
                if ok
                else t.get("msg_exchange_request_skipped")
            )
            or ("交换请求已创建" if ok else "交换请求创建失败"),
        }
    )


@router.get("/management/exchange-cards")
async def get_management_exchange_cards(
    account_id: str | None = Query(default=None),
    status: str | None = Query(default=None),
    q: str = Query(default=""),
    sort_by: str = Query(default="created_at"),
    sort_order: str = Query(default="desc"),
    page: int = Query(default=0),
    page_size: int = Query(default=10),
    session: Session = Depends(get_fastapi_session),
):
    """获取交换卡页面数据。"""
    context = build_exchange_card_context(
        session=session,
        account_id=parse_optional_int(account_id),
        status=status or None,
        q=q,
        sort_by=sort_by,
        sort_order=sort_order,
        page=page,
        page_size=page_size,
    )
    return json_response(context)


@router.post("/management/exchange-cards/{request_id}/cancel")
async def post_exchange_cancel(request_id: int):
    """取消交换请求。"""
    ok = cancel_exchange_request(request_id=request_id)
    _, t = get_current_i18n()
    return json_response(
        {
            "ok": ok,
            "message": (
                t.get("msg_exchange_request_cancelled")
                if ok
                else t.get("msg_exchange_request_cancel_failed")
            )
            or ("交换请求已取消" if ok else "交换请求取消失败"),
        }
    )
