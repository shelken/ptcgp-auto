import os

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse, JSONResponse
from fastapi.responses import HTMLResponse
from sqlmodel import Session

from ptcgp_auto_v2.config.assets import build_card_image_bases
from ptcgp_auto_v2.db.engine import get_fastapi_session
from ptcgp_auto_v2.web.services.index_service import build_index_context
from ptcgp_auto_v2.web.utils.i18n import get_current_i18n


router = APIRouter()


@router.get("/", response_class=HTMLResponse)
async def read_root(
):
    """渲染 React 入口。"""
    current_dir = os.path.dirname(os.path.abspath(__file__))
    dist_index_path = os.path.join(current_dir, "..", "frontend", "dist", "index.html")
    if os.path.exists(dist_index_path):
        return FileResponse(dist_index_path)

    raise HTTPException(status_code=500, detail="frontend_dist_not_found")


@router.get("/api/react/bootstrap", response_class=JSONResponse)
async def react_bootstrap(
    session: Session = Depends(get_fastapi_session),
):
    """提供 React 首屏初始化数据。"""
    current_lang, t = get_current_i18n()
    context = build_index_context(session)
    image_bases = build_card_image_bases(current_lang)
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
            "assets": {
                "card_proxy_base_url": image_bases["proxy_base_url"],
                "card_cdn_base_url": image_bases["cdn_base_url"],
            },
        }
    )
