# -*- coding: utf-8 -*-
"""React API - 元数据与每日送卡路由。"""

from __future__ import annotations

from collections.abc import Mapping

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlmodel import Session

from ptcgp_auto_v2.db.engine import get_fastapi_session
from ptcgp_auto_v2.web.routers.react_api_common import json_response
from ptcgp_auto_v2.web.services.daily_gift_service import build_daily_gift_context
from ptcgp_auto_v2.web.services.metadata_service import (
    build_metadata_context,
    check_metadata_sources,
    execute_metadata_sync,
    preview_metadata_sync,
)
from ptcgp_auto_v2.web.utils.form_utils import parse_optional_int


router = APIRouter()


def _build_daily_gift_query_params(raw: Mapping[str, object]) -> dict[str, object]:
    """统一解析每日送卡页面查询参数。"""
    return {
        "biz_date_local": raw.get("biz_date_local"),
        "account_id": parse_optional_int(raw.get("account_id")),
        "sort_by": str(raw.get("sort_by") or "updated_at"),
        "sort_order": str(raw.get("sort_order") or "desc"),
        "page": parse_optional_int(raw.get("page")) or 0,
        "page_size": parse_optional_int(raw.get("page_size")) or 10,
        "pair_page": parse_optional_int(raw.get("pair_page")) or 0,
        "pair_page_size": parse_optional_int(raw.get("pair_page_size")) or 10,
    }


@router.get("/management/metadata")
async def get_management_metadata(
    selected_node_type: str = Query(default="root"),
    selected_node_id: str = Query(default="all"),
    selected_set_code: str = Query(default=""),
    selected_pack_name: str = Query(default=""),
    ui_step: int = Query(default=1),
    current_action: str = Query(default="update_new_series"),
    snapshot_id: str = Query(default=""),
):
    """获取元数据管理页面数据。"""
    return json_response(
        build_metadata_context(
            ui_step=ui_step,
            selected_node_type=selected_node_type,
            selected_node_id=selected_node_id,
            selected_set_code=selected_set_code,
            selected_pack_name=selected_pack_name,
            snapshot_id=snapshot_id,
            current_action=current_action,
        )
    )


@router.post("/management/metadata/preview")
async def post_metadata_preview(request: Request):
    """生成元数据预览。"""
    body = await request.json()
    action = str(body.get("action") or "update_new_series")
    node_type = str(body.get("node_type") or "root")
    node_id = str(body.get("node_id") or "all")
    force_refresh = bool(body.get("force_refresh", False))

    result = preview_metadata_sync(
        node_type=node_type,
        node_id=node_id,
        action=action,
        force_refresh=force_refresh,
    )
    return json_response(result)


@router.post("/management/metadata/execute")
async def post_metadata_execute(request: Request):
    """执行元数据同步。"""
    body = await request.json()
    snapshot_id = str(body.get("snapshot_id") or "")
    if not snapshot_id:
        raise HTTPException(status_code=400, detail="snapshot_id_required")
    result = execute_metadata_sync(snapshot_id)
    return json_response(result)


@router.post("/management/metadata/check")
async def post_metadata_check():
    """检查元数据源状态。"""
    return json_response(check_metadata_sources())


@router.get("/management/daily-gift")
async def get_management_daily_gift(
    biz_date_local: str | None = Query(default=None),
    account_id: str | None = Query(default=None),
    sort_by: str = Query(default="updated_at"),
    sort_order: str = Query(default="desc"),
    page: int = Query(default=0),
    page_size: int = Query(default=10),
    pair_page: int = Query(default=0),
    pair_page_size: int = Query(default=10),
    session: Session = Depends(get_fastapi_session),
):
    """获取每日送卡页面数据。"""
    query_params = _build_daily_gift_query_params(
        {
            "biz_date_local": biz_date_local,
            "account_id": account_id,
            "sort_by": sort_by,
            "sort_order": sort_order,
            "page": page,
            "page_size": page_size,
            "pair_page": pair_page,
            "pair_page_size": pair_page_size,
        }
    )
    return json_response(
        build_daily_gift_context(
            session=session,
            **query_params,
        )
    )
