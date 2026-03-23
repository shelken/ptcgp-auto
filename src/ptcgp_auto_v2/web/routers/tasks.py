import json

from fastapi import APIRouter, Depends, Request, Query
from fastapi.responses import HTMLResponse
from sqlmodel import Session

from ptcgp_auto_v2.core.scheduling_service import (
    TASK_SORT_BY_DISPATCH_PRIORITY,
    normalize_task_sort,
)
from ptcgp_auto_v2.db.engine import get_fastapi_session
from ptcgp_auto_v2.web.services.task_service import (
    build_task_list_render_context,
    list_task_filter_accounts,
    reset_completed_tasks_by_filters,
)
from ptcgp_auto_v2.web.utils.response_utils import render_template
from ptcgp_auto_v2.web.utils.form_utils import parse_optional_int
from ptcgp_auto_v2.web.utils.i18n import get_current_i18n
from ptcgp_auto_v2.web.utils.filter_utils import normalize_page, normalize_page_size


router = APIRouter()


@router.get("/management/tasks", response_class=HTMLResponse)
async def get_management_tasks(
    request: Request,
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
    """渲染任务管理列表。"""
    page = normalize_page(page)
    page_size = normalize_page_size(page_size)
    normalized_status = [item for item in status if item]
    normalized_task_type = [item for item in task_type if item]
    sort_by, sort_order = normalize_task_sort(sort_by, sort_order)
    parsed_account_id: int | None = None
    if account_id:
        account_id_str = str(account_id).strip()
        if account_id_str.isdigit():
            parsed_account_id = int(account_id_str)

    context = build_task_list_render_context(
        session=session,
        page=page,
        page_size=page_size,
        status=normalized_status,
        task_type=normalized_task_type,
        account_id=parsed_account_id,
        account_q=account_q,
        sort_by=sort_by,
        sort_order=sort_order,
        table_only=False,
    )
    return render_template(request, "partials/task_list.html", context)


@router.get("/management/tasks/reset-completed-modal", response_class=HTMLResponse)
async def get_reset_completed_modal(
    request: Request,
    status: list[str] = Query(default=[]),
    task_type: list[str] = Query(default=[]),
    account_id: str | None = Query(default=None),
    sort_by: str = Query(default=TASK_SORT_BY_DISPATCH_PRIORITY),
    sort_order: str = Query(default="asc"),
):
    """渲染重置完成任务确认弹窗。"""
    current_lang, t = get_current_i18n()

    normalized_status = [item for item in status if item]
    normalized_task_type = [item for item in task_type if item]
    sort_by, sort_order = normalize_task_sort(sort_by, sort_order)
    parsed_account_id = parse_optional_int(account_id)

    return render_template(
        request,
        "partials/modals/reset_tasks_confirm.html",
        {
            "t": t,
            "current_lang": current_lang,
            "selected_status": normalized_status,
            "selected_task_type": normalized_task_type,
            "selected_account_id": parsed_account_id,
            "selected_sort_by": sort_by,
            "selected_sort_order": sort_order,
        },
    )


@router.post("/api/tasks/reset-completed", response_class=HTMLResponse)
async def reset_completed_tasks(
    request: Request,
    session: Session = Depends(get_fastapi_session),
):
    """按筛选条件将完成任务重置为待执行。"""
    form = await request.form()
    status = [item for item in form.getlist("status") if isinstance(item, str) and item]
    task_type = [
        item for item in form.getlist("task_type") if isinstance(item, str) and item
    ]
    parsed_account_id = parse_optional_int(form.get("account_id"))
    sort_by = str(form.get("sort_by") or TASK_SORT_BY_DISPATCH_PRIORITY)
    sort_order = str(form.get("sort_order") or "asc")
    sort_by, sort_order = normalize_task_sort(sort_by, sort_order)

    reset_count = reset_completed_tasks_by_filters(
        session=session,
        status=status,
        task_type=task_type,
        account_id=parsed_account_id,
    )

    current_lang, t = get_current_i18n()
    context = build_task_list_render_context(
        session=session,
        page=0,
        page_size=10,
        status=status,
        task_type=task_type,
        account_id=parsed_account_id,
        account_q="",
        sort_by=sort_by,
        sort_order=sort_order,
        table_only=True,
    )

    response = render_template(
        request,
        "partials/task_list.html",
        context,
    )
    if reset_count > 0:
        message_template = t.get("msg_reset_completed_done") or "已重置 {count} 个任务"
        message = message_template.replace("{count}", str(reset_count))
    else:
        message = t.get("msg_reset_completed_empty") or "没有需要重置的任务"
    response.headers["HX-Trigger"] = json.dumps(
        {"showToast": {"message": message}}, ensure_ascii=True
    )
    return response


@router.get("/api/tasks", response_class=HTMLResponse)
async def get_tasks(
    request: Request,
    page: int = 0,
    page_size: int = 10,
    status: list[str] = Query(default=[]),
    task_type: list[str] = Query(default=[]),
    account_id: str | None = Query(default=None),
    account_q: str = Query(default=""),
    sort_by: str = Query(default=TASK_SORT_BY_DISPATCH_PRIORITY),
    sort_order: str = Query(default="asc"),
    session: Session = Depends(get_fastapi_session),
):
    """获取任务列表（HTMX）。"""
    page = normalize_page(page)
    page_size = normalize_page_size(page_size)
    normalized_status = [item for item in status if item]
    normalized_task_type = [item for item in task_type if item]
    sort_by, sort_order = normalize_task_sort(sort_by, sort_order)
    parsed_account_id: int | None = None
    if account_id:
        account_id_str = str(account_id).strip()
        if account_id_str.isdigit():
            parsed_account_id = int(account_id_str)

    context = build_task_list_render_context(
        session=session,
        page=page,
        page_size=page_size,
        status=normalized_status,
        task_type=normalized_task_type,
        account_id=parsed_account_id,
        account_q=account_q,
        sort_by=sort_by,
        sort_order=sort_order,
        table_only=True,
    )

    return render_template(
        request,
        "partials/task_list.html",
        context,
    )


@router.get("/api/tasks/account-options", response_class=HTMLResponse)
async def get_task_account_options(
    request: Request,
    q: str = Query(default=""),
    session: Session = Depends(get_fastapi_session),
):
    """返回任务筛选账号远程搜索候选。"""
    accounts = list_task_filter_accounts(session=session, q=q, limit=20)
    return render_template(
        request,
        "partials/task_account_options.html",
        {
            "accounts": accounts,
            "query": q,
        },
    )
