from fastapi import APIRouter, Depends, Request, Query
from fastapi.responses import HTMLResponse
from sqlmodel import Session

from ptcgp_auto_v2.db.engine import get_fastapi_session
from ptcgp_auto_v2.web.services.account_service import (
    build_accounts_list_context,
    build_account_edit_context,
    update_account_details,
)
from ptcgp_auto_v2.web.utils.form_utils import safe_get_string
from ptcgp_auto_v2.web.utils.response_utils import render_template


router = APIRouter()


async def _render_management_accounts(
    request: Request,
    session: Session,
    q: str = "",
    sort_by: str = "id",
    sort_order: str = "asc",
    page: int = 0,
    page_size: int = 10,
):
    """渲染账号管理列表（内部复用，避免 Query 默认对象泄漏）。"""
    context = build_accounts_list_context(
        session=session,
        q=q,
        sort_by=sort_by,
        sort_order=sort_order,
        page=page,
        page_size=page_size,
    )
    return render_template(request, "partials/account_list.html", context)


@router.get("/management/accounts", response_class=HTMLResponse)
async def get_management_accounts(
    request: Request,
    q: str = Query(default=""),
    sort_by: str = Query(default="id"),
    sort_order: str = Query(default="asc"),
    page: int = Query(default=0),
    page_size: int = Query(default=10),
    session: Session = Depends(get_fastapi_session),
):
    """渲染账号管理列表。"""
    return await _render_management_accounts(
        request=request,
        session=session,
        q=q,
        sort_by=sort_by,
        sort_order=sort_order,
        page=page,
        page_size=page_size,
    )


@router.get("/management/accounts/{account_id}/edit", response_class=HTMLResponse)
async def get_account_edit_modal(
    request: Request,
    account_id: int,
):
    """渲染账号编辑弹窗。"""
    context = build_account_edit_context(account_id)
    if not context:
        return HTMLResponse("Account not found", status_code=404)
    return render_template(request, "partials/modals/edit_account.html", context)


@router.post("/api/accounts/{account_id}/details")
async def update_account_details_api(
    request: Request,
    account_id: int,
    session: Session = Depends(get_fastapi_session),
):
    """更新账号昵称与备注。"""
    form = await request.form()
    nickname = safe_get_string(form, "nickname") or ""
    remark = safe_get_string(form, "remark") or ""
    update_account_details(account_id, nickname, remark)

    response = await _render_management_accounts(
        request=request,
        session=session,
        q="",
        sort_by="id",
        sort_order="asc",
        page=0,
        page_size=10,
    )
    response.headers["HX-Trigger"] = "closeModal"
    return response
