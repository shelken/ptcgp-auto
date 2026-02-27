import json

from fastapi import APIRouter, Depends, Request, Query
from fastapi.responses import HTMLResponse
from sqlmodel import Session

from ptcgp_auto_v2.db.engine import get_fastapi_session
from ptcgp_auto_v2.web.services.exchange_card_service import create_exchange_request_with_task
from ptcgp_auto_v2.web.services.owned_card_service import (
    build_owned_cards_list_context,
    build_owned_card_modal_context,
    build_owned_card_exchange_accounts_context,
)
from ptcgp_auto_v2.web.utils.form_utils import parse_optional_int, safe_get_string
from ptcgp_auto_v2.web.utils.i18n import get_current_lang, get_translations
from ptcgp_auto_v2.web.utils.response_utils import render_template


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
    session: Session = Depends(get_fastapi_session),
):
    """获取已拥有卡牌列表。"""
    context = build_owned_cards_list_context(
        session=session,
        page=page,
        page_size=page_size,
        account_id=account_id,
        rarity=rarity,
        card_type=card_type,
        set_code=set_code,
        pack_name=pack_name,
        element=element,
        sort_by=sort_by,
    )
    if not context["items"] and page > 0:
        return ""
    return render_template(request, "partials/owned_card_list.html", context)


@router.get("/api/owned-cards/modal", response_class=HTMLResponse)
async def get_owned_card_modal(
    request: Request,
    card_id: int,
    session: Session = Depends(get_fastapi_session),
):
    """获取已拥有卡牌详情弹窗。"""
    current_lang = get_current_lang()
    context = build_owned_card_modal_context(session, card_id)
    if not context:
        t = get_translations(current_lang)
        return HTMLResponse(
            t.get("owned_cards_not_found", "Card not found"), status_code=404
        )
    return render_template(request, "partials/modals/owned_card_detail.html", context)


@router.get("/api/owned-cards/modal/exchange-accounts", response_class=HTMLResponse)
async def get_owned_card_modal_exchange_accounts(
    request: Request,
    card_id: int,
    page: int = Query(default=0),
    page_size: int = Query(default=10),
    q: str = Query(default=""),
    sort_by: str = Query(default="account_id"),
    sort_order: str = Query(default="asc"),
    session: Session = Depends(get_fastapi_session),
):
    """获取已拥有卡牌弹窗中的交换账号分页表格。"""
    context = build_owned_card_exchange_accounts_context(
        session=session,
        card_id=card_id,
        page=page,
        page_size=page_size,
        q=q,
        sort_by=sort_by,
        sort_order=sort_order,
    )
    return render_template(
        request,
        "partials/modals/owned_card_exchange_accounts_table.html",
        context,
    )


@router.post("/api/exchange-cards/requests", response_class=HTMLResponse)
async def create_exchange_request(
    request: Request,
):
    """从拥有卡牌弹窗创建交换请求。"""
    current_lang = get_current_lang()
    t = get_translations(current_lang)
    form = await request.form()

    from_account_id = parse_optional_int(form.get("from_account_id"))
    to_account_id = parse_optional_int(form.get("to_account_id"))
    to_friend_id = safe_get_string(form, "to_friend_id") or ""
    target_card_id = parse_optional_int(form.get("target_card_id"))
    target_card_rarity = safe_get_string(form, "target_card_rarity") or ""

    created = False
    if from_account_id and target_card_id and to_friend_id:
        created = create_exchange_request_with_task(
            from_account_id=from_account_id,
            to_account_id=to_account_id,
            to_friend_id=to_friend_id,
            target_card_id=target_card_id,
            target_card_rarity=target_card_rarity,
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
