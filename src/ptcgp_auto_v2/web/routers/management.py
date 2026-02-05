from fastapi import APIRouter, Depends, Request, Query
from fastapi.responses import HTMLResponse
from sqlmodel import Session

from ptcgp_auto_v2.db.engine import get_fastapi_session
from ptcgp_auto_v2.web.services.account_service import (
    get_accounts_context,
    build_account_edit_context,
    update_account_details,
)
from ptcgp_auto_v2.web.utils.form_utils import safe_get_string
from ptcgp_auto_v2.web.utils.i18n import detect_lang
from ptcgp_auto_v2.web.utils.template_env import get_templates


router = APIRouter()


@router.get("/management/accounts", response_class=HTMLResponse)
async def get_management_accounts(
    request: Request,
    lang: str | None = Query(default=None),
    session: Session = Depends(get_fastapi_session),
):
    """渲染账号管理列表。"""
    current_lang = detect_lang(request, lang)
    context = get_accounts_context(session, current_lang)
    context["request"] = request
    templates = get_templates()
    return templates.TemplateResponse("partials/account_list.html", context)


@router.get("/management/accounts/{account_id}/edit", response_class=HTMLResponse)
async def get_account_edit_modal(
    request: Request,
    account_id: int,
    lang: str | None = Query(default=None),
):
    """渲染账号编辑弹窗。"""
    current_lang = detect_lang(request, lang)
    context = build_account_edit_context(account_id, current_lang)
    if not context:
        return HTMLResponse("Account not found", status_code=404)
    context["request"] = request
    templates = get_templates()
    return templates.TemplateResponse("partials/modals/edit_account.html", context)


@router.post("/api/accounts/{account_id}/details")
async def update_account_details_api(
    request: Request,
    account_id: int,
    lang: str | None = Query(default=None),
    session: Session = Depends(get_fastapi_session),
):
    """更新账号昵称与备注。"""
    form = await request.form()
    nickname = safe_get_string(form, "nickname") or ""
    remark = safe_get_string(form, "remark") or ""
    update_account_details(account_id, nickname, remark)

    response = await get_management_accounts(request, lang=lang, session=session)
    response.headers["HX-Trigger"] = "closeModal"
    return response
