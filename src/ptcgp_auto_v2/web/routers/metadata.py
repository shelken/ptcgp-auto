from fastapi import APIRouter, Request, Query
from fastapi.responses import HTMLResponse

from ptcgp_auto_v2.web.services.metadata_service import (
    build_metadata_context,
    update_set_label,
    update_pack_label,
)
from ptcgp_auto_v2.web.utils.form_utils import safe_get_string
from ptcgp_auto_v2.web.utils.i18n import detect_lang
from ptcgp_auto_v2.web.utils.template_env import get_templates


router = APIRouter()


@router.get("/management/metadata", response_class=HTMLResponse)
async def get_management_metadata(
    request: Request,
    lang: str | None = Query(default=None),
):
    """渲染元数据管理页面。"""
    current_lang = detect_lang(request, lang)
    context = build_metadata_context(current_lang)
    context["request"] = request
    templates = get_templates()
    return templates.TemplateResponse("partials/metadata_list.html", context)


@router.post("/api/metadata/set/{code}/label")
async def update_set_label_api(
    request: Request,
    code: str,
    lang: str | None = Query(default=None),
):
    """更新卡包系列中文名。"""
    form = await request.form()
    label_zh = safe_get_string(form, "label_zh") or ""
    update_set_label(code, label_zh)
    return await get_management_metadata(request, lang=lang)


@router.post("/api/metadata/pack/{name}/label")
async def update_pack_label_api(
    request: Request,
    name: str,
    lang: str | None = Query(default=None),
):
    """更新补充包中文名。"""
    form = await request.form()
    label_zh = safe_get_string(form, "label_zh") or ""
    update_pack_label(name, label_zh)
    return await get_management_metadata(request, lang=lang)
