from fastapi import APIRouter, Depends, Request, Query
from fastapi.responses import HTMLResponse
from sqlmodel import Session

from ptcgp_auto_v2.db.engine import get_fastapi_session
from ptcgp_auto_v2.web.services.record_service import build_records_list_context
from ptcgp_auto_v2.web.utils.response_utils import render_template
from ptcgp_auto_v2.web.utils.filter_utils import normalize_page, normalize_page_size


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
    context = build_records_list_context(
        session=session,
        page=normalize_page(page),
        page_size=normalize_page_size(page_size),
        rarity=[item for item in rarity if item],
        card_type=[item for item in card_type if item],
    )
    return render_template(request, "partials/record_list.html", context)
