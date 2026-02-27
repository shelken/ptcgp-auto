import json

from fastapi import APIRouter, Depends, Request, Query
from fastapi.responses import HTMLResponse
from sqlmodel import Session

from ptcgp_auto_v2.core.task_ordering import (
    TASK_SORT_BY_DISPATCH_PRIORITY,
    normalize_task_sort,
)
from ptcgp_auto_v2.core.task_base import TaskRegistry
from ptcgp_auto_v2.core.task_status import TaskStatus
from ptcgp_auto_v2.db.engine import get_fastapi_session
from ptcgp_auto_v2.db.repositories import AccountRepository
from ptcgp_auto_v2.web.services.task_service import (
    list_task_status_view,
    build_tasks_page_url,
    reset_completed_tasks_by_filters,
)
from ptcgp_auto_v2.web.utils.form_utils import parse_optional_int
from ptcgp_auto_v2.web.utils.i18n import get_current_lang, get_translations
from ptcgp_auto_v2.web.utils.template_env import get_templates


router = APIRouter()


@router.get("/management/tasks", response_class=HTMLResponse)
async def get_management_tasks(
    request: Request,
    status: list[str] = Query(default=[]),
    task_type: list[str] = Query(default=[]),
    account_id: str | None = Query(default=None),
    page: int = Query(default=0),
    page_size: int = Query(default=10),
    sort_by: str = Query(default=TASK_SORT_BY_DISPATCH_PRIORITY),
    sort_order: str = Query(default="asc"),
    session: Session = Depends(get_fastapi_session),
):
    """渲染任务管理列表。"""
    current_lang = get_current_lang()
    t = get_translations(current_lang)
    repo = AccountRepository()
    accounts = repo.get_all()
    status_options = [status.value for status in TaskStatus]
    task_types = TaskRegistry.all_types()

    page = max(page, 0)
    page_size = min(max(page_size, 1), 100)
    normalized_status = [item for item in status if item]
    normalized_task_type = [item for item in task_type if item]
    sort_by, sort_order = normalize_task_sort(sort_by, sort_order)
    parsed_account_id: int | None = None
    if account_id:
        account_id_str = str(account_id).strip()
        if account_id_str.isdigit():
            parsed_account_id = int(account_id_str)

    tasks, has_more = list_task_status_view(
        session=session,
        page=page,
        page_size=page_size,
        status=normalized_status,
        task_type=normalized_task_type,
        account_id=parsed_account_id,
        sort_by=sort_by,
        sort_order=sort_order,
    )
    next_page_url = build_tasks_page_url(
        page + 1,
        current_lang,
        status=normalized_status,
        task_type=normalized_task_type,
        account_id=parsed_account_id,
        sort_by=sort_by,
        sort_order=sort_order,
    )
    prev_page_url = build_tasks_page_url(
        page - 1,
        current_lang,
        status=normalized_status,
        task_type=normalized_task_type,
        account_id=parsed_account_id,
        sort_by=sort_by,
        sort_order=sort_order,
    )

    templates = get_templates()
    return templates.TemplateResponse(
        "partials/task_list.html",
        {
            "request": request,
            "tasks": tasks,
            "has_more": has_more,
            "has_prev": page > 0,
            "next_page_url": next_page_url,
            "prev_page_url": prev_page_url,
            "page": page,
            "page_size": page_size,
            "status_options": status_options,
            "task_types": task_types,
            "accounts": accounts,
            "selected_status": normalized_status,
            "selected_task_type": normalized_task_type,
            "selected_account_id": parsed_account_id,
            "selected_sort_by": sort_by,
            "selected_sort_order": sort_order,
            "table_only": False,
            "t": t,
            "current_lang": current_lang,
        },
    )


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
    current_lang = get_current_lang()
    t = get_translations(current_lang)

    normalized_status = [item for item in status if item]
    normalized_task_type = [item for item in task_type if item]
    sort_by, sort_order = normalize_task_sort(sort_by, sort_order)
    parsed_account_id = parse_optional_int(account_id)

    templates = get_templates()
    return templates.TemplateResponse(
        "partials/modals/reset_tasks_confirm.html",
        {
            "request": request,
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

    current_lang = get_current_lang()
    t = get_translations(current_lang)
    page = 0
    page_size = 10
    tasks, has_more = list_task_status_view(
        session=session,
        page=page,
        page_size=page_size,
        status=status,
        task_type=task_type,
        account_id=parsed_account_id,
        sort_by=sort_by,
        sort_order=sort_order,
    )
    next_page_url = build_tasks_page_url(
        page + 1,
        current_lang,
        status=status,
        task_type=task_type,
        account_id=parsed_account_id,
        sort_by=sort_by,
        sort_order=sort_order,
    )
    prev_page_url = build_tasks_page_url(
        page - 1,
        current_lang,
        status=status,
        task_type=task_type,
        account_id=parsed_account_id,
        sort_by=sort_by,
        sort_order=sort_order,
    )

    templates = get_templates()
    response = templates.TemplateResponse(
        "partials/task_list.html",
        {
            "request": request,
            "tasks": tasks,
            "has_more": has_more,
            "has_prev": page > 0,
            "next_page_url": next_page_url,
            "prev_page_url": prev_page_url,
            "page": page,
            "page_size": page_size,
            "table_only": True,
            "t": t,
            "current_lang": current_lang,
        },
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
    sort_by: str = Query(default=TASK_SORT_BY_DISPATCH_PRIORITY),
    sort_order: str = Query(default="asc"),
    session: Session = Depends(get_fastapi_session),
):
    """获取任务列表（HTMX）。"""
    current_lang = get_current_lang()
    t = get_translations(current_lang)
    repo = AccountRepository()
    accounts = repo.get_all()
    status_options = [status_item.value for status_item in TaskStatus]
    task_types = TaskRegistry.all_types()

    page = max(page, 0)
    page_size = min(max(page_size, 1), 100)
    normalized_status = [item for item in status if item]
    normalized_task_type = [item for item in task_type if item]
    sort_by, sort_order = normalize_task_sort(sort_by, sort_order)
    parsed_account_id: int | None = None
    if account_id:
        account_id_str = str(account_id).strip()
        if account_id_str.isdigit():
            parsed_account_id = int(account_id_str)

    tasks, has_more = list_task_status_view(
        session=session,
        page=page,
        page_size=page_size,
        status=normalized_status,
        task_type=normalized_task_type,
        account_id=parsed_account_id,
        sort_by=sort_by,
        sort_order=sort_order,
    )
    if not tasks and page > 0:
        return ""

    next_page_url = build_tasks_page_url(
        page + 1,
        current_lang,
        status=normalized_status,
        task_type=normalized_task_type,
        account_id=parsed_account_id,
        sort_by=sort_by,
        sort_order=sort_order,
    )
    prev_page_url = build_tasks_page_url(
        page - 1,
        current_lang,
        status=normalized_status,
        task_type=normalized_task_type,
        account_id=parsed_account_id,
        sort_by=sort_by,
        sort_order=sort_order,
    )

    templates = get_templates()
    return templates.TemplateResponse(
        "partials/task_list.html",
        {
            "request": request,
            "tasks": tasks,
            "has_more": has_more,
            "has_prev": page > 0,
            "next_page_url": next_page_url,
            "prev_page_url": prev_page_url,
            "page": page,
            "page_size": page_size,
            "status_options": status_options,
            "task_types": task_types,
            "accounts": accounts,
            "selected_status": normalized_status,
            "selected_task_type": normalized_task_type,
            "selected_account_id": parsed_account_id,
            "selected_sort_by": sort_by,
            "selected_sort_order": sort_order,
            "table_only": True,
            "t": t,
            "current_lang": current_lang,
        },
    )
