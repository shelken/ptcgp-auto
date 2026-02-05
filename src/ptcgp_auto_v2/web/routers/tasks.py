from fastapi import APIRouter, Depends, Request, Query
from fastapi.responses import HTMLResponse
from sqlmodel import Session

from ptcgp_auto_v2.core.task_base import TaskRegistry, TaskStatus
from ptcgp_auto_v2.db.engine import get_fastapi_session
from ptcgp_auto_v2.db.repositories import AccountRepository
from ptcgp_auto_v2.web.services.task_service import (
    list_task_status_view,
    build_tasks_page_url,
)
from ptcgp_auto_v2.web.utils.i18n import detect_lang, get_translations
from ptcgp_auto_v2.web.utils.template_env import get_templates


router = APIRouter()


@router.get("/management/tasks", response_class=HTMLResponse)
async def get_management_tasks(
    request: Request,
    lang: str | None = Query(default=None),
    status: list[str] = Query(default=[]),
    task_type: list[str] = Query(default=[]),
    account_id: str | None = Query(default=None),
    session: Session = Depends(get_fastapi_session),
):
    """渲染任务管理列表。"""
    current_lang = detect_lang(request, lang)
    t = get_translations(current_lang)
    repo = AccountRepository()
    accounts = repo.get_all()
    status_options = [status.value for status in TaskStatus]
    task_types = TaskRegistry.all_types()

    page = 0
    page_size = 50
    normalized_status = [item for item in status if item]
    normalized_task_type = [item for item in task_type if item]
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
    )
    next_page_url = build_tasks_page_url(
        page + 1,
        current_lang,
        status=normalized_status,
        task_type=normalized_task_type,
        account_id=parsed_account_id,
    )

    templates = get_templates()
    return templates.TemplateResponse(
        "partials/task_list.html",
        {
            "request": request,
            "tasks": tasks,
            "has_more": has_more,
            "next_page_url": next_page_url,
            "page": page,
            "page_size": page_size,
            "status_options": status_options,
            "task_types": task_types,
            "accounts": accounts,
            "selected_status": normalized_status,
            "selected_task_type": normalized_task_type,
            "selected_account_id": parsed_account_id,
            "table_only": False,
            "t": t,
            "current_lang": current_lang,
        },
    )


@router.get("/api/tasks", response_class=HTMLResponse)
async def get_tasks(
    request: Request,
    page: int = 0,
    page_size: int = 50,
    status: list[str] = Query(default=[]),
    task_type: list[str] = Query(default=[]),
    account_id: str | None = Query(default=None),
    lang: str | None = Query(default=None),
    session: Session = Depends(get_fastapi_session),
):
    """获取任务列表（HTMX）。"""
    current_lang = detect_lang(request, lang)
    t = get_translations(current_lang)
    repo = AccountRepository()
    accounts = repo.get_all()
    status_options = [status_item.value for status_item in TaskStatus]
    task_types = TaskRegistry.all_types()

    normalized_status = [item for item in status if item]
    normalized_task_type = [item for item in task_type if item]
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
    )
    if not tasks and page > 0:
        return ""

    next_page_url = build_tasks_page_url(
        page + 1,
        current_lang,
        status=normalized_status,
        task_type=normalized_task_type,
        account_id=parsed_account_id,
    )

    templates = get_templates()
    return templates.TemplateResponse(
        "partials/task_list.html",
        {
            "request": request,
            "tasks": tasks,
            "has_more": has_more,
            "next_page_url": next_page_url,
            "page": page,
            "page_size": page_size,
            "status_options": status_options,
            "task_types": task_types,
            "accounts": accounts,
            "selected_status": normalized_status,
            "selected_task_type": normalized_task_type,
            "selected_account_id": parsed_account_id,
            "table_only": True,
            "t": t,
            "current_lang": current_lang,
        },
    )
