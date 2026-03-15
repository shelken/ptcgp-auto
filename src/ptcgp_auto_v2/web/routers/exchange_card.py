# -*- coding: utf-8 -*-
"""交换卡牌管理路由。"""

import json

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import HTMLResponse
from sqlmodel import Session

from ptcgp_auto_v2.db.engine import get_fastapi_session
from ptcgp_auto_v2.web.services.exchange_card_service import (
    build_exchange_card_context,
    cancel_exchange_request,
)
from ptcgp_auto_v2.web.utils.form_utils import parse_optional_int
from ptcgp_auto_v2.web.utils.i18n import get_current_i18n
from ptcgp_auto_v2.web.utils.response_utils import render_template


router = APIRouter()


@router.get("/management/exchange-cards", response_class=HTMLResponse)
async def get_management_exchange_cards(
    request: Request,
    account_id: str | None = Query(default=None),
    status: str | None = Query(default=None),
    q: str = Query(default=""),
    sort_by: str = Query(default="created_at"),
    sort_order: str = Query(default="desc"),
    page: int = Query(default=0),
    page_size: int = Query(default=10),
    session: Session = Depends(get_fastapi_session),
):
    """渲染交换记录管理页面。"""
    context = build_exchange_card_context(
        session=session,
        account_id=parse_optional_int(account_id),
        status=status or None,
        q=q,
        sort_by=sort_by,
        sort_order=sort_order,
        page=max(page, 0),
        page_size=min(max(page_size, 1), 100),
    )
    return render_template(request, "partials/exchange_card_list.html", context)


@router.post(
    "/api/exchange-cards/requests/{request_id}/cancel",
    response_class=HTMLResponse,
)
async def post_cancel_exchange_request(
    request_id: int,
    request: Request,
    account_id: str | None = Query(default=None),
    status: str | None = Query(default=None),
    q: str = Query(default=""),
    sort_by: str = Query(default="created_at"),
    sort_order: str = Query(default="desc"),
    page: int = Query(default=0),
    page_size: int = Query(default=10),
    session: Session = Depends(get_fastapi_session),
):
    """取消交换请求。"""
    cancelled = cancel_exchange_request(request_id=request_id)
    response = await get_management_exchange_cards(
        request=request,
        account_id=account_id,
        status=status,
        q=q,
        sort_by=sort_by,
        sort_order=sort_order,
        page=page,
        page_size=page_size,
        session=session,
    )
    _, t = get_current_i18n()
    message = (
        t.get("msg_exchange_request_cancelled")
        if cancelled
        else t.get("msg_exchange_request_cancel_failed")
    ) or ("交换请求已取消" if cancelled else "交换请求取消失败")
    response.headers["HX-Trigger"] = json.dumps(
        {"showToast": {"message": message}},
        ensure_ascii=True,
    )
    return response
