# -*- coding: utf-8 -*-
"""React API - 开包记录路由。"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlmodel import Session

from ptcgp_auto_v2.db.engine import get_fastapi_session
from ptcgp_auto_v2.web.routers.react_api_common import (
    json_response,
    normalize_pagination_params,
)
from ptcgp_auto_v2.web.services.record_service import build_records_list_context


router = APIRouter()


@router.get("/records")
async def get_records(
    page: int = Query(default=0),
    page_size: int = Query(default=10),
    rarity: list[str] = Query(default=[]),
    card_type: list[str] = Query(default=[]),
    session: Session = Depends(get_fastapi_session),
):
    """获取开包记录数据。"""
    normalized_page, normalized_page_size = normalize_pagination_params(
        page=page,
        page_size=page_size,
    )
    context = build_records_list_context(
        session=session,
        page=normalized_page,
        page_size=normalized_page_size,
        rarity=[item for item in rarity if item],
        card_type=[item for item in card_type if item],
    )
    return json_response(context)
