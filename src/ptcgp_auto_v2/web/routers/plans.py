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
    build_plans_list_context,
    build_plan_edit_context,
    upsert_plan_from_form,
    delete_plan_by_id,
)
from ptcgp_auto_v2.web.utils.i18n import get_current_lang, get_translations
from ptcgp_auto_v2.web.utils.response_utils import render_template


router = APIRouter()


async def _render_management_plans(
    request: Request,
    session: Session,
    q: str = "",
    sort_by: str = "id",
    sort_order: str = "asc",
    page: int = 0,
    page_size: int = 10,
):
    """渲染计划管理列表（内部复用，避免 Query 默认对象泄漏）。"""
    context = build_plans_list_context(
        session=session,
        q=q,
        sort_by=sort_by,
        sort_order=sort_order,
        page=page,
        page_size=page_size,
    )
    return render_template(request, "partials/plan_list.html", context)


@router.get("/management/plans", response_class=HTMLResponse)
async def get_management_plans(
    request: Request,
    q: str = Query(default=""),
    sort_by: str = Query(default="id"),
    sort_order: str = Query(default="asc"),
    page: int = Query(default=0),
    page_size: int = Query(default=10),
    session: Session = Depends(get_fastapi_session),
):
    """渲染计划管理列表。"""
    return await _render_management_plans(
        request=request,
        session=session,
        q=q,
        sort_by=sort_by,
        sort_order=sort_order,
        page=page,
        page_size=page_size,
    )


@router.get("/management/plans/edit", response_class=HTMLResponse)
async def get_plan_edit_modal(
    request: Request,
    plan_id: int | None = Query(None),
):
    """渲染计划编辑弹窗。"""
    context = build_plan_edit_context(plan_id)
    return render_template(request, "partials/modals/edit_plan.html", context)


@router.post("/api/plans")
async def save_plan(
    request: Request,
    session: Session = Depends(get_fastapi_session),
):
    """保存计划数据。"""
    form = await request.form()
    duplicate_name = upsert_plan_from_form(form)

    if duplicate_name is not None:
        # 名称重复，返回 toast 提示但不关闭弹窗
        current_lang = get_current_lang()
        t = get_translations(current_lang)
        msg_tpl = t.get("msg_plan_name_duplicate", "Plan name '{name}' already exists")
        message = msg_tpl.replace("{name}", duplicate_name)
        response = HTMLResponse("", status_code=422)
        response.headers["HX-Reswap"] = "none"
        response.headers["HX-Trigger"] = json.dumps(
            {"showToast": {"message": message}}, ensure_ascii=True
        )
        return response

    response = await _render_management_plans(
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


@router.delete("/api/plans/{plan_id}")
async def delete_plan(
    request: Request,
    plan_id: int,
    session: Session = Depends(get_fastapi_session),
):
    """删除计划。"""
    delete_plan_by_id(plan_id)
    return await _render_management_plans(
        request=request,
        session=session,
        q="",
        sort_by="id",
        sort_order="asc",
        page=0,
        page_size=10,
    )


@router.get("/management/accounts/{account_id}/plans", response_class=HTMLResponse)
async def get_account_plans_modal(
    request: Request,
    account_id: int,
    session: Session = Depends(get_fastapi_session),
):
    """渲染账号计划编辑弹窗。"""
    context = build_account_plans_context(session, account_id)
    if not context:
        return HTMLResponse("Account not found", status_code=404)
    return render_template(request, "partials/modals/edit_account_plans.html", context)


@router.post("/api/accounts/{account_id}/plans")
async def update_account_plans_api(
    request: Request,
    account_id: int,
):
    """更新账号计划关联。"""
    try:
        data = await request.json()
    except Exception:
        return HTMLResponse("Invalid JSON", status_code=400)

    update_account_plans(account_id, data)
    return {"status": "ok"}
