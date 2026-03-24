import os

from fastapi import APIRouter, Depends, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.responses import HTMLResponse
from sqlmodel import Session

from ptcgp_auto_v2.db.engine import get_fastapi_session
from ptcgp_auto_v2.web.services.index_service import build_index_context
from ptcgp_auto_v2.web.utils.i18n import get_current_i18n
from ptcgp_auto_v2.web.utils.response_utils import render_template


router = APIRouter()


@router.get("/", response_class=HTMLResponse)
async def read_root(
    request: Request,
    session: Session = Depends(get_fastapi_session),
):
    """渲染 React 入口；若构建产物不存在则降级到旧版首页。"""
    current_dir = os.path.dirname(os.path.abspath(__file__))
    dist_index_path = os.path.join(current_dir, "..", "frontend", "dist", "index.html")
    if os.path.exists(dist_index_path):
        return FileResponse(dist_index_path)

    context = build_index_context(session)
    return render_template(request, "index.html", context)


@router.get("/legacy", response_class=HTMLResponse)
async def read_legacy_root(
    request: Request,
    session: Session = Depends(get_fastapi_session),
):
    """渲染旧版 HTMX 首页（迁移期保留）。"""
    context = build_index_context(session)
    return render_template(request, "index.html", context)


@router.get("/api/react/bootstrap", response_class=JSONResponse)
async def react_bootstrap(
    session: Session = Depends(get_fastapi_session),
):
    """提供 React 首屏初始化数据。"""
    current_lang, t = get_current_i18n()
    context = build_index_context(session)
    return JSONResponse(
        {
            "lang": current_lang,
            "t": t,
            "options": {
                "rarities": context["rarities"],
                "card_types": context["card_types"],
                "elements": context["elements"],
                "card_sets": context["card_sets"],
                "packs": context["packs"],
            },
        }
    )
