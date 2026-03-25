# -*- coding: utf-8 -*-
"""React API - 账号与计划路由。"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlmodel import Session

from ptcgp_auto_v2.db.engine import get_fastapi_session
from ptcgp_auto_v2.web.routers.react_api_common import json_response
from ptcgp_auto_v2.web.services.account_service import (
    build_account_edit_context,
    build_account_plans_context,
    build_accounts_list_context,
    update_account_details,
    update_account_plans,
)
from ptcgp_auto_v2.web.services.pack_config_service import (
    build_card_sets_options,
    build_pack_config_context,
    build_save_account_pack_config,
    build_set_boosters_options,
)
from ptcgp_auto_v2.web.services.plan_service import (
    build_plan_edit_context,
    build_plans_list_context,
    delete_plan_by_id,
    upsert_plan_from_form,
)
from ptcgp_auto_v2.web.utils.i18n import get_current_i18n


router = APIRouter()


@router.get("/management/accounts")
async def get_management_accounts(
    q: str = Query(default=""),
    sort_by: str = Query(default="id"),
    sort_order: str = Query(default="asc"),
    page: int = Query(default=0),
    page_size: int = Query(default=10),
    session: Session = Depends(get_fastapi_session),
):
    """获取账号管理数据。"""
    return json_response(
        build_accounts_list_context(
            session=session,
            q=q,
            sort_by=sort_by,
            sort_order=sort_order,
            page=page,
            page_size=page_size,
        )
    )


@router.get("/management/accounts/{account_id}")
async def get_management_account(account_id: int):
    """获取账号编辑数据。"""
    context = build_account_edit_context(account_id)
    if context is None:
        raise HTTPException(status_code=404, detail="account_not_found")
    return json_response(context)


@router.put("/management/accounts/{account_id}")
async def update_management_account(request: Request, account_id: int):
    """更新账号信息。"""
    body = await request.json()
    nickname = str(body.get("nickname") or "")
    remark = str(body.get("remark") or "")
    update_account_details(account_id, nickname, remark)
    _, t = get_current_i18n()
    return json_response({"ok": True, "message": t.get("msg_saved") or "已保存"})


@router.get("/management/accounts/{account_id}/plans")
async def get_account_plans(
    account_id: int,
    session: Session = Depends(get_fastapi_session),
):
    """获取账号计划关联数据。"""
    context = build_account_plans_context(session, account_id)
    if context is None:
        raise HTTPException(status_code=404, detail="account_not_found")
    return json_response(context)


@router.put("/management/accounts/{account_id}/plans")
async def put_account_plans(request: Request, account_id: int):
    """更新账号计划关联。"""
    data = await request.json()
    if not isinstance(data, list):
        raise HTTPException(status_code=400, detail="invalid_payload")
    update_account_plans(account_id, data)
    return json_response({"ok": True})


@router.get("/management/accounts/{account_id}/pack-config")
async def get_account_pack_config(account_id: int):
    """获取账号开包配置。"""
    return json_response(build_pack_config_context(account_id))


@router.put("/management/accounts/{account_id}/pack-config")
async def put_account_pack_config(request: Request, account_id: int):
    """保存账号开包配置。"""
    body = await request.json()
    set_code = str(body.get("set_code") or "")
    booster_name = str(body.get("booster_name") or "")
    build_save_account_pack_config(account_id, set_code, booster_name)
    _, t = get_current_i18n()
    return json_response({"ok": True, "message": t.get("msg_saved") or "已保存"})


@router.get("/management/card-sets")
async def get_card_sets():
    """获取卡包系列。"""
    return json_response(build_card_sets_options())


@router.get("/management/card-sets/{set_code}/boosters")
async def get_set_boosters(set_code: str):
    """获取系列补充包。"""
    return json_response(build_set_boosters_options(set_code))


@router.get("/management/plans")
async def get_management_plans(
    q: str = Query(default=""),
    sort_by: str = Query(default="id"),
    sort_order: str = Query(default="asc"),
    page: int = Query(default=0),
    page_size: int = Query(default=10),
    session: Session = Depends(get_fastapi_session),
):
    """获取计划管理数据。"""
    return json_response(
        build_plans_list_context(
            session=session,
            q=q,
            sort_by=sort_by,
            sort_order=sort_order,
            page=page,
            page_size=page_size,
        )
    )


@router.get("/management/plans/edit")
async def get_plan_edit(plan_id: int | None = Query(default=None)):
    """获取计划编辑数据。"""
    return json_response(build_plan_edit_context(plan_id))


@router.post("/management/plans")
async def save_plan(request: Request):
    """保存计划。"""
    form = await request.form()
    duplicate_name = upsert_plan_from_form(form)
    if duplicate_name:
        _, t = get_current_i18n()
        msg_tpl = t.get("msg_plan_name_duplicate", "Plan name '{name}' already exists")
        return json_response(
            {
                "ok": False,
                "message": msg_tpl.replace("{name}", duplicate_name),
                "error": "duplicate_name",
            }
        )
    _, t = get_current_i18n()
    return json_response({"ok": True, "message": t.get("msg_saved") or "已保存"})


@router.delete("/management/plans/{plan_id}")
async def delete_plan(plan_id: int):
    """删除计划。"""
    delete_plan_by_id(plan_id)
    _, t = get_current_i18n()
    return json_response({"ok": True, "message": t.get("msg_deleted") or "已删除"})
