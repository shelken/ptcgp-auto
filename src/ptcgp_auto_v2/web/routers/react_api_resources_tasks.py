# -*- coding: utf-8 -*-
"""React API - 资源与任务路由。"""

from __future__ import annotations

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
    parsed_account_id: int | None = None
    if account_id:
        val = account_id.strip()
        if val.isdigit():
            parsed_account_id = int(val)

    normalized_status = [item for item in status if item]
    normalized_task_type = [item for item in task_type if item]
    sort_by, sort_order = normalize_task_sort(sort_by, sort_order)
    normalized_page, normalized_page_size = normalize_pagination_params(
        page=page,
        page_size=page_size,
    )

    return json_response(
        build_task_list_render_context(
            session=session,
            page=normalized_page,
            page_size=normalized_page_size,
            status=normalized_status,
            task_type=normalized_task_type,
            account_id=parsed_account_id,
            account_q=account_q,
            sort_by=sort_by,
            sort_order=sort_order,
            table_only=False,
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
    status = [item for item in body.get("status", []) if isinstance(item, str) and item]
    task_type = [
        item for item in body.get("task_type", []) if isinstance(item, str) and item
    ]
    account_id = parse_optional_int(body.get("account_id"))
    account_q = str(body.get("account_q") or "").strip()

    reset_count = reset_completed_tasks_by_filters(
        session=session,
        status=status,
        task_type=task_type,
        account_id=account_id,
        account_q=account_q,
    )
    _, t = get_current_i18n()
    if reset_count > 0:
        message_template = t.get("msg_reset_completed_done") or "已重置 {count} 个任务"
        message = message_template.replace("{count}", str(reset_count))
    else:
        message = t.get("msg_reset_completed_empty") or "没有需要重置的任务"
    return json_response({"ok": True, "count": reset_count, "message": message})
