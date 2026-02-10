from fastapi import APIRouter, Depends, Request, Query
from fastapi.responses import HTMLResponse
from sqlmodel import Session

from ptcgp_auto_v2.db.engine import get_fastapi_session
from ptcgp_auto_v2.web.services.owned_card_service import (
    list_owned_cards,
    build_owned_card_modal_context,
)
from ptcgp_auto_v2.web.utils.i18n import detect_lang, get_translations
from ptcgp_auto_v2.web.utils.template_env import get_templates


router = APIRouter()


@router.get("/api/owned-cards", response_class=HTMLResponse)
async def get_owned_cards(
    request: Request,
    page: int = 0,
    page_size: int = 60,
    account_id: str | None = Query(default=None),
    rarity: list[str] = Query(default=[]),
    card_type: list[str] = Query(default=[]),
    set_code: list[str] = Query(default=[]),
    pack_name: list[str] = Query(default=[]),
    element: list[str] = Query(default=[]),
    sort_by: str = Query(default="acquired"),
    lang: str | None = Query(default=None),
):
    """获取已拥有卡牌列表。"""
    current_lang = detect_lang(request, lang)
    result = list_owned_cards(
        page,
        page_size,
        account_id,
        rarity,
        card_type,
        set_code,
        pack_name,
        element,
        sort_by,
        current_lang,
    )
    if result.get("stop"):
        return ""
    result["request"] = request
    templates = get_templates()
    return templates.TemplateResponse("partials/owned_card_list.html", result)


@router.get("/api/owned-cards/modal", response_class=HTMLResponse)
async def get_owned_card_modal(
    request: Request,
    card_id: int,
    lang: str | None = Query(default=None),
    session: Session = Depends(get_fastapi_session),
):
    """获取已拥有卡牌详情弹窗。"""
    current_lang = detect_lang(request, lang)
    context = build_owned_card_modal_context(session, card_id, current_lang)
    if not context:
        t = get_translations(current_lang)
        return HTMLResponse(
            t.get("owned_cards_not_found", "Card not found"), status_code=404
        )
    context["request"] = request
    templates = get_templates()
    return templates.TemplateResponse("partials/modals/owned_card_detail.html", context)
