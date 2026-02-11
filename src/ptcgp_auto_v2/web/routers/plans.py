from fastapi import APIRouter, Request, Query, Depends
from fastapi.responses import HTMLResponse
from sqlmodel import Session

import json

from ptcgp_auto_v2.db.engine import get_fastapi_session
from ptcgp_auto_v2.web.services.account_service import (
    build_account_plans_context,
    update_account_plans,
)
from ptcgp_auto_v2.web.services.plan_service import (
    get_plans_context,
    build_plan_edit_context,
    upsert_plan_from_form,
    delete_plan_by_id,
)
from ptcgp_auto_v2.web.utils.i18n import detect_lang, get_translations, normalize_lang
from ptcgp_auto_v2.web.utils.template_env import get_templates


router = APIRouter()


@router.get("/management/plans", response_class=HTMLResponse)
async def get_management_plans(
    request: Request,
    lang: str | None = Query(default=None),
):
    """渲染计划管理列表。"""
    current_lang = detect_lang(request, lang)
    context = get_plans_context(current_lang)
    context["request"] = request
    templates = get_templates()
    return templates.TemplateResponse("partials/plan_list.html", context)


@router.get("/management/plans/edit", response_class=HTMLResponse)
async def get_plan_edit_modal(
    request: Request,
    plan_id: int | None = Query(None),
    lang: str | None = Query(default=None),
):
    """渲染计划编辑弹窗。"""
    current_lang = detect_lang(request, lang)
    context = build_plan_edit_context(plan_id, current_lang)
    context["request"] = request
    templates = get_templates()
    return templates.TemplateResponse("partials/modals/edit_plan.html", context)


@router.post("/api/plans")
async def save_plan(
    request: Request,
    lang: str | None = Query(default=None),
):
    """保存计划数据。"""
    form = await request.form()
    duplicate_name = upsert_plan_from_form(form)

    if duplicate_name is not None:
        # 名称重复，返回 toast 提示但不关闭弹窗
        current_lang = normalize_lang(detect_lang(request, lang))
        t = get_translations(current_lang)
        msg_tpl = t.get("msg_plan_name_duplicate", "Plan name '{name}' already exists")
        message = msg_tpl.replace("{name}", duplicate_name)
        response = HTMLResponse("", status_code=422)
        response.headers["HX-Reswap"] = "none"
        response.headers["HX-Trigger"] = json.dumps(
            {"showToast": {"message": message}}, ensure_ascii=True
        )
        return response

    response = await get_management_plans(request, lang=lang)
    response.headers["HX-Trigger"] = "closeModal"
    return response


@router.delete("/api/plans/{plan_id}")
async def delete_plan(
    request: Request,
    plan_id: int,
    lang: str | None = Query(default=None),
):
    """删除计划。"""
    delete_plan_by_id(plan_id)
    return await get_management_plans(request, lang=lang)


@router.get("/management/accounts/{account_id}/plans", response_class=HTMLResponse)
async def get_account_plans_modal(
    request: Request,
    account_id: int,
    lang: str | None = Query(default=None),
    session: Session = Depends(get_fastapi_session),
):
    """渲染账号计划编辑弹窗。"""
    current_lang = detect_lang(request, lang)
    context = build_account_plans_context(session, account_id, current_lang)
    if not context:
        return HTMLResponse("Account not found", status_code=404)
    context["request"] = request
    templates = get_templates()
    return templates.TemplateResponse(
        "partials/modals/edit_account_plans.html", context
    )


@router.post("/api/accounts/{account_id}/plans")
async def update_account_plans_api(
    request: Request,
    account_id: int,
    lang: str | None = Query(default=None),
):
    """更新账号计划关联。"""
    try:
        data = await request.json()
    except Exception:
        return HTMLResponse("Invalid JSON", status_code=400)

    update_account_plans(account_id, data)
    return {"status": "ok"}
