from fastapi import APIRouter, Depends, Request, Query
from fastapi.responses import HTMLResponse
from sqlmodel import Session

from ptcgp_auto_v2.db.engine import get_fastapi_session
from ptcgp_auto_v2.web.services.record_service import build_records_context
from ptcgp_auto_v2.web.utils.template_env import get_templates


router = APIRouter()


@router.get("/api/records", response_class=HTMLResponse)
async def get_records(
    request: Request,
    page: int = 0,
    page_size: int = 10,
    rarity: list[str] = Query(default=[]),
    card_type: list[str] = Query(default=[]),
    session: Session = Depends(get_fastapi_session),
):
    """获取开包记录列表。"""
    result = build_records_context(session, page, page_size, rarity, card_type)
    if result.get("stop"):
        return ""
    result["request"] = request
    templates = get_templates()
    return templates.TemplateResponse("partials/record_list.html", result)
