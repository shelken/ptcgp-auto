from fastapi import APIRouter, Depends, Request, Query
from fastapi.responses import HTMLResponse
from sqlmodel import Session

from ptcgp_auto_v2.db.engine import get_fastapi_session
from ptcgp_auto_v2.web.services.index_service import build_index_context
from ptcgp_auto_v2.web.utils.i18n import detect_lang
from ptcgp_auto_v2.web.utils.template_env import get_templates


router = APIRouter()


@router.get("/", response_class=HTMLResponse)
async def read_root(
    request: Request,
    lang: str | None = Query(default=None),
    session: Session = Depends(get_fastapi_session),
):
    """渲染首页。"""
    current_lang = detect_lang(request, lang)
    context = build_index_context(session, current_lang)
    context["request"] = request
    templates = get_templates()
    return templates.TemplateResponse("index.html", context)
