from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import HTMLResponse
from sqlmodel import Session

from ptcgp_auto_v2.db.engine import get_fastapi_session
from ptcgp_auto_v2.web.services.daily_gift_service import build_daily_gift_context
from ptcgp_auto_v2.web.utils.i18n import detect_lang
from ptcgp_auto_v2.web.utils.template_env import get_templates


router = APIRouter()


@router.get("/management/daily-gift", response_class=HTMLResponse)
async def get_management_daily_gift(
    request: Request,
    lang: str | None = Query(default=None),
    biz_date_local: str | None = Query(default=None),
    session: Session = Depends(get_fastapi_session),
):
    """渲染每日送卡管理页面。"""
    current_lang = detect_lang(request, lang)
    context = build_daily_gift_context(
        session=session,
        lang=current_lang,
        biz_date_local=biz_date_local,
    )
    context["request"] = request
    templates = get_templates()
    return templates.TemplateResponse("partials/daily_gift_list.html", context)
