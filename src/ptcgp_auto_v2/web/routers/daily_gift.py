from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import HTMLResponse
from sqlmodel import Session

from ptcgp_auto_v2.db.engine import get_fastapi_session
from ptcgp_auto_v2.web.services.daily_gift_service import build_daily_gift_context
from ptcgp_auto_v2.web.utils.form_utils import parse_optional_int
from ptcgp_auto_v2.web.utils.response_utils import render_template


router = APIRouter()


@router.get("/management/daily-gift", response_class=HTMLResponse)
async def get_management_daily_gift(
    request: Request,
    biz_date_local: str | None = Query(default=None),
    account_id: str | None = Query(default=None),
    q: str = Query(default=""),
    sort_by: str = Query(default="updated_at"),
    sort_order: str = Query(default="desc"),
    page: int = Query(default=0),
    page_size: int = Query(default=10),
    pair_page: int = Query(default=0),
    pair_page_size: int = Query(default=10),
    session: Session = Depends(get_fastapi_session),
):
    """渲染每日送卡管理页面。"""
    context = build_daily_gift_context(
        session=session,
        biz_date_local=biz_date_local,
        account_id=parse_optional_int(account_id),
        q=q,
        sort_by=sort_by,
        sort_order=sort_order,
        page=max(page, 0),
        page_size=min(max(page_size, 1), 100),
        pair_page=max(pair_page, 0),
        pair_page_size=min(max(pair_page_size, 1), 100),
    )
    return render_template(request, "partials/daily_gift_list.html", context)
