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
from ptcgp_auto_v2.web.utils.i18n import detect_lang
from ptcgp_auto_v2.web.utils.template_env import get_templates


router = APIRouter()


@router.get("/management/exchange-cards", response_class=HTMLResponse)
async def get_management_exchange_cards(
    request: Request,
    lang: str | None = Query(default=None),
    account_id: str | None = Query(default=None),
    status: str | None = Query(default=None),
    session: Session = Depends(get_fastapi_session),
):
    """渲染交换记录管理页面。"""
    current_lang = detect_lang(request, lang)
    context = build_exchange_card_context(
        session=session,
        lang=current_lang,
        account_id=parse_optional_int(account_id),
        status=status or None,
    )
    context["request"] = request
    templates = get_templates()
    return templates.TemplateResponse("partials/exchange_card_list.html", context)


@router.post(
    "/api/exchange-cards/requests/{request_id}/cancel",
    response_class=HTMLResponse,
)
async def post_cancel_exchange_request(
    request_id: int,
    request: Request,
    lang: str | None = Query(default=None),
    account_id: str | None = Query(default=None),
    status: str | None = Query(default=None),
    session: Session = Depends(get_fastapi_session),
):
    """取消交换请求。"""
    cancelled = cancel_exchange_request(request_id=request_id)
    response = await get_management_exchange_cards(
        request=request,
        lang=lang,
        account_id=account_id,
        status=status,
        session=session,
    )
    context = build_exchange_card_context(
        session=session, lang=detect_lang(request, lang)
    )
    t = context["t"]
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
