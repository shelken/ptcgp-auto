from fastapi import APIRouter, Depends, Request, Query
from fastapi.responses import HTMLResponse
from sqlmodel import Session

from ptcgp_auto_v2.db.engine import get_fastapi_session
from ptcgp_auto_v2.web.services.record_service import list_records
from ptcgp_auto_v2.web.utils.i18n import detect_lang
from ptcgp_auto_v2.web.utils.template_env import get_templates


router = APIRouter()


@router.get("/api/records", response_class=HTMLResponse)
async def get_records(
    request: Request,
    page: int = 0,
    page_size: int = 10,
    rarity: list[str] = Query(default=[]),
    card_type: list[str] = Query(default=[]),
    lang: str | None = Query(default=None),
    session: Session = Depends(get_fastapi_session),
):
    """获取开包记录列表。"""
    current_lang = detect_lang(request, lang)
    result = list_records(session, page, page_size, rarity, card_type, current_lang)
    if result.get("stop"):
        return ""
    result["request"] = request
    templates = get_templates()
    return templates.TemplateResponse("partials/record_list.html", result)
