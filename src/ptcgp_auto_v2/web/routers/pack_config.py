from fastapi import APIRouter, Depends, Request, Query
from fastapi.responses import HTMLResponse
from sqlmodel import Session

from ptcgp_auto_v2.db.engine import get_fastapi_session
from ptcgp_auto_v2.web.services.pack_config_service import (
    list_card_sets,
    list_set_boosters,
    build_pack_config_context,
    save_account_pack_config,
)
from ptcgp_auto_v2.web.services.account_service import build_accounts_list_context
from ptcgp_auto_v2.web.utils.form_utils import safe_get_string
from ptcgp_auto_v2.web.utils.response_utils import render_template


router = APIRouter()


@router.get("/api/card-sets")
async def get_card_sets():
    """获取卡包系列列表。"""
    return list_card_sets()


@router.get("/api/card-sets/{set_code}/boosters")
async def get_set_boosters(set_code: str):
    """获取指定系列补充包列表。"""
    return list_set_boosters(set_code)


@router.get(
    "/management/accounts/{account_id}/pack-config", response_class=HTMLResponse
)
async def get_account_pack_config_modal(
    request: Request,
    account_id: int,
):
    """渲染补充包配置弹窗。"""
    context = build_pack_config_context(account_id)
    return render_template(request, "partials/modals/edit_pack_config.html", context)


@router.get("/partials/boosters-options", response_class=HTMLResponse)
async def get_boosters_options(
    request: Request,
    pack_code: str = Query(...),
):
    """获取补充包选项 HTML。"""
    boosters = list_set_boosters(pack_code)
    return render_template(
        request, "partials/options_boosters.html", {"boosters": boosters}
    )


@router.post("/api/accounts/{account_id}/pack-config")
async def save_account_pack_config_api(
    request: Request,
    account_id: int,
    session: Session = Depends(get_fastapi_session),
):
    """保存账号补充包配置。"""
    form = await request.form()
    pack_code = safe_get_string(form, "pack_code") or ""
    booster_name = safe_get_string(form, "booster_name") or ""

    save_account_pack_config(account_id, pack_code, booster_name)

    context = build_accounts_list_context(session=session)
    response = render_template(request, "partials/account_list.html", context)
    response.headers["HX-Trigger"] = "closeModal"
    return response
