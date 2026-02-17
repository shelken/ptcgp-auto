import json

from fastapi import APIRouter, Depends, Request, Query
from fastapi.responses import HTMLResponse
from sqlmodel import Session

from ptcgp_auto_v2.db.engine import get_fastapi_session
from ptcgp_auto_v2.db.repositories import TaskInstanceRepository
from ptcgp_auto_v2.services import ExchangeCardService
from ptcgp_auto_v2.web.services.owned_card_service import (
    list_owned_cards,
    build_owned_card_modal_context,
    build_owned_card_exchange_accounts_context,
)
from ptcgp_auto_v2.web.utils.form_utils import parse_optional_int, safe_get_string
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


@router.get("/api/owned-cards/modal/exchange-accounts", response_class=HTMLResponse)
async def get_owned_card_modal_exchange_accounts(
    request: Request,
    card_id: int,
    page: int = Query(default=0),
    page_size: int = Query(default=12),
    q: str = Query(default=""),
    sort_by: str = Query(default="account_id"),
    sort_order: str = Query(default="asc"),
    lang: str | None = Query(default=None),
    session: Session = Depends(get_fastapi_session),
):
    """获取已拥有卡牌弹窗中的交换账号分页表格。"""
    current_lang = detect_lang(request, lang)
    context = build_owned_card_exchange_accounts_context(
        session=session,
        card_id=card_id,
        lang=current_lang,
        page=page,
        page_size=page_size,
        q=q,
        sort_by=sort_by,
        sort_order=sort_order,
    )
    context["request"] = request
    templates = get_templates()
    return templates.TemplateResponse(
        "partials/modals/owned_card_exchange_accounts_table.html", context
    )


@router.post("/api/exchange-cards/requests", response_class=HTMLResponse)
async def create_exchange_request(
    request: Request,
    lang: str | None = Query(default=None),
):
    """从拥有卡牌弹窗创建交换请求。"""
    current_lang = detect_lang(request, lang)
    t = get_translations(current_lang)
    form = await request.form()

    from_account_id = parse_optional_int(form.get("from_account_id"))
    to_account_id = parse_optional_int(form.get("to_account_id"))
    to_friend_id = safe_get_string(form, "to_friend_id") or ""
    target_card_id = parse_optional_int(form.get("target_card_id"))
    target_card_rarity = safe_get_string(form, "target_card_rarity") or ""

    created = None
    if from_account_id and target_card_id and to_friend_id:
        created = ExchangeCardService.create_request(
            from_account_id=from_account_id,
            to_account_id=to_account_id,
            to_friend_id=to_friend_id,
            target_card_id=target_card_id,
            target_card_rarity=target_card_rarity,
        )
        if created is not None:
            TaskInstanceRepository().ensure_pending(
                account_id=from_account_id,
                task_type="exchange_cards",
                reset_type="once",
            )

    message = (
        t.get("msg_exchange_request_created")
        if created
        else t.get("msg_exchange_request_skipped")
    ) or ("交换请求已创建" if created else "交换请求创建失败")

    response = HTMLResponse(status_code=204)
    response.headers["HX-Trigger"] = json.dumps(
        {
            "closeModal": True,
            "showToast": {"message": message},
        },
        ensure_ascii=True,
    )
    return response
