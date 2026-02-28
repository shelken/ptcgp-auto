from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from sqlmodel import Session

from ptcgp_auto_v2.db.engine import get_fastapi_session
from ptcgp_auto_v2.web.services.index_service import build_index_context
from ptcgp_auto_v2.web.utils.response_utils import render_template


router = APIRouter()


@router.get("/", response_class=HTMLResponse)
async def read_root(
    request: Request,
    session: Session = Depends(get_fastapi_session),
):
    """渲染首页。"""
    context = build_index_context(session)
    return render_template(request, "index.html", context)
