# -*- coding: utf-8 -*-
"""React API - 开包记录路由。"""

from __future__ import annotations

from collections.abc import Mapping

from fastapi import APIRouter, Depends, Query
from sqlmodel import Session

from ptcgp_auto_v2.db.engine import get_fastapi_session
from ptcgp_auto_v2.web.routers.react_api_common import json_response
from ptcgp_auto_v2.web.services.record_service import (
    build_records_list_context,
    build_records_list_query_state,
)
from ptcgp_auto_v2.web.utils.form_utils import parse_optional_int


router = APIRouter()


def _normalize_string_list(raw: object) -> list[str]:
    """统一过滤空值和非字符串项。"""
    if not isinstance(raw, list):
        return []
    return [item for item in raw if isinstance(item, str)]


def _build_records_query_params(raw: Mapping[str, object]) -> dict[str, object]:
    """统一解析 records 查询参数。"""
    page = parse_optional_int(raw.get("page"))
    page_size = parse_optional_int(raw.get("page_size"))
    list_state = build_records_list_query_state(
        page=page if page is not None else 0,
        page_size=page_size if page_size is not None else 10,
        rarity=_normalize_string_list(raw.get("rarity")),
        card_type=_normalize_string_list(raw.get("card_type")),
        set_code=_normalize_string_list(raw.get("set_code")),
        card_name_query=str(raw.get("q") or ""),
    )
    return {
        "page": list_state.page,
        "page_size": list_state.page_size,
        "rarity": list_state.rarity,
        "card_type": list_state.card_type,
        "set_code": list_state.set_code,
        "card_name_query": list_state.card_name_query,
    }


@router.get("/records")
async def get_records(
    page: int = Query(default=0),
    page_size: int = Query(default=10),
    rarity: list[str] = Query(default=[]),
    card_type: list[str] = Query(default=[]),
    set_code: list[str] = Query(default=[]),
    q: str = Query(default=""),
    session: Session = Depends(get_fastapi_session),
):
    """获取开包记录数据。"""
    query_params = _build_records_query_params(
        {
            "page": page,
            "page_size": page_size,
            "rarity": rarity,
            "card_type": card_type,
            "set_code": set_code,
            "q": q,
        }
    )
    context = build_records_list_context(
        session=session,
        **query_params,
    )
    return json_response(context)
