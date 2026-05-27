# -*- coding: utf-8 -*-
"""React API - 资源与任务路由。"""

from __future__ import annotations

from collections.abc import Mapping

from fastapi import APIRouter, Depends, Query, Request
from sqlmodel import Session

from ptcgp_auto_v2.core.scheduling_service import (
    TASK_SORT_BY_DISPATCH_PRIORITY,
    normalize_task_sort,
)
from ptcgp_auto_v2.db.engine import get_fastapi_session
from ptcgp_auto_v2.web.routers.react_api_common import (
    json_response,
    normalize_pagination_params,
)
from ptcgp_auto_v2.web.services.resource_service import build_resources_context
from ptcgp_auto_v2.web.services.task_service import (
    build_task_list_render_context,
    list_task_filter_accounts,
    reset_completed_tasks_by_filters,
)
from ptcgp_auto_v2.web.utils.form_utils import parse_optional_int
from ptcgp_auto_v2.web.utils.i18n import get_current_i18n


router = APIRouter()


def _normalize_string_list(raw: object) -> list[str]:
    """统一过滤空值与非字符串项，保持多选筛选语义一致。"""
    if not isinstance(raw, list):
        return []
    return [item for item in raw if isinstance(item, str) and item]


def _build_task_filter_params(raw: Mapping[str, object]) -> dict[str, object]:
    """统一解析任务筛选范围，供列表与批量动作复用。"""
    return {
        "status": _normalize_string_list(raw.get("status")),
        "task_type": _normalize_string_list(raw.get("task_type")),
        "account_id": parse_optional_int(raw.get("account_id")),
        "account_q": str(raw.get("account_q") or "").strip(),
    }


def _build_task_list_query_params(raw: Mapping[str, object]) -> dict[str, object]:
    """统一解析任务列表查询参数。"""
    sort_by, sort_order = normalize_task_sort(
        str(raw.get("sort_by") or TASK_SORT_BY_DISPATCH_PRIORITY),
        str(raw.get("sort_order") or "asc"),
    )
    page = parse_optional_int(raw.get("page"))
    page_size = parse_optional_int(raw.get("page_size"))
    normalized_page, normalized_page_size = normalize_pagination_params(
        page=page if page is not None else 0,
        page_size=page_size if page_size is not None else 10,
    )
    return {
        **_build_task_filter_params(raw),
        "sort_by": sort_by,
        "sort_order": sort_order,
        "page": normalized_page,
        "page_size": normalized_page_size,
    }


@router.get("/management/resources")
async def get_management_resources(
    view: str = Query(default="stats"),
    q: str = Query(default=""),
    sort_by: str = Query(default="id"),
    sort_order: str = Query(default="asc"),
    page: int = Query(default=0),
    page_size: int = Query(default=20),
    session: Session = Depends(get_fastapi_session),
):
    """获取资源管理数据。"""
    return json_response(
        build_resources_context(
            session=session,
            view=view,
            q=q,
            sort_by=sort_by,
            sort_order=sort_order,
            page=page,
            page_size=page_size,
        )
    )


@router.get("/management/tasks")
async def get_management_tasks(
    status: list[str] = Query(default=[]),
    task_type: list[str] = Query(default=[]),
    account_id: str | None = Query(default=None),
    account_q: str = Query(default=""),
    page: int = Query(default=0),
    page_size: int = Query(default=10),
    sort_by: str = Query(default=TASK_SORT_BY_DISPATCH_PRIORITY),
    sort_order: str = Query(default="asc"),
    session: Session = Depends(get_fastapi_session),
):
    """获取任务管理数据。"""
    query_params = _build_task_list_query_params(
        {
            "status": status,
            "task_type": task_type,
            "account_id": account_id,
            "account_q": account_q,
            "sort_by": sort_by,
            "sort_order": sort_order,
            "page": page,
            "page_size": page_size,
        }
    )

    return json_response(
        build_task_list_render_context(
            session=session,
            **query_params,
        )
    )


@router.get("/management/tasks/account-options")
async def get_task_account_options(
    q: str = Query(default=""),
    session: Session = Depends(get_fastapi_session),
):
    """获取任务筛选账号候选。"""
    return json_response({"accounts": list_task_filter_accounts(session=session, q=q, limit=20)})


@router.post("/management/tasks/reset-completed")
async def post_reset_completed_tasks(
    request: Request,
    session: Session = Depends(get_fastapi_session),
):
    """按筛选条件重置已完成任务。"""
    body = await request.json()
    filter_params = _build_task_filter_params(body)

    reset_count = reset_completed_tasks_by_filters(
        session=session,
        **filter_params,
    )
    _, t = get_current_i18n()
    if reset_count > 0:
        message_template = t.get("msg_reset_completed_done") or "已重置 {count} 个任务"
        message = message_template.replace("{count}", str(reset_count))
    else:
        message = t.get("msg_reset_completed_empty") or "没有需要重置的任务"
    return json_response({"ok": True, "count": reset_count, "message": message})
