# -*- coding: utf-8 -*-
"""React API - 好友关系路由。"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Request
from sqlmodel import Session

from ptcgp_auto_v2.db.engine import get_fastapi_session
from ptcgp_auto_v2.db.models import Account
from ptcgp_auto_v2.web.routers.react_api_common import json_response
from ptcgp_auto_v2.web.services.friendship_service import (
    build_friendship_context,
    cancel_pending_request,
    create_add_request,
    create_delete_request,
)
from ptcgp_auto_v2.web.utils.filter_utils import normalize_page, normalize_page_size
from ptcgp_auto_v2.web.utils.form_utils import parse_optional_int
from ptcgp_auto_v2.web.utils.i18n import get_current_i18n


router = APIRouter()


@router.get("/management/friendships")
async def get_management_friendships(
    account_id: str | None = Query(default=None),
    from_account_id: str | None = Query(default=None),
    q: str = Query(default=""),
    sort_by: str = Query(default="created_at"),
    sort_order: str = Query(default="desc"),
    page: int = Query(default=0),
    page_size: int = Query(default=10),
    session: Session = Depends(get_fastapi_session),
):
    """获取好友管理页面数据。"""
    context = build_friendship_context(
        session=session,
        account_id=parse_optional_int(account_id),
        from_account_id=parse_optional_int(from_account_id),
        q=q,
        sort_by=sort_by,
        sort_order=sort_order,
        page=normalize_page(page),
        page_size=normalize_page_size(page_size),
    )
    return json_response(context)


@router.post("/management/friendships/add")
async def post_friendship_add(
    request: Request,
    session: Session = Depends(get_fastapi_session),
):
    """创建添加好友请求。"""
    body = await request.json()
    from_account_id = parse_optional_int(body.get("from_account_id"))
    to_account_id = parse_optional_int(body.get("to_account_id"))
    to_friend_id = str(body.get("to_friend_id") or "").strip()

    if not to_friend_id and to_account_id:
        target_account = session.get(Account, to_account_id)
        if target_account and target_account.friend_id:
            to_friend_id = target_account.friend_id

    ok = bool(
        from_account_id
        and to_friend_id
        and create_add_request(
            from_account_id=from_account_id,
            to_friend_id=to_friend_id,
            to_account_id=to_account_id,
        )
    )
    _, t = get_current_i18n()
    return json_response(
        {
            "ok": ok,
            "message": (
                t.get("msg_add_request_created")
                if ok
                else t.get("msg_add_request_skipped")
            )
            or ("添加请求已创建" if ok else "无效或重复请求，未创建添加申请"),
        }
    )


@router.post("/management/friendships/delete")
async def post_friendship_delete(
    request: Request,
    session: Session = Depends(get_fastapi_session),
):
    """创建删除好友请求。"""
    body = await request.json()
    from_account_id = parse_optional_int(body.get("from_account_id"))
    to_account_id = parse_optional_int(body.get("to_account_id"))
    friend_id = str(body.get("friend_id") or "").strip()

    if not friend_id and to_account_id:
        target_account = session.get(Account, to_account_id)
        if target_account and target_account.friend_id:
            friend_id = target_account.friend_id

    ok = bool(
        from_account_id
        and friend_id
        and create_delete_request(
            from_account_id=from_account_id,
            friend_id=friend_id,
            to_account_id=to_account_id,
        )
    )
    _, t = get_current_i18n()
    return json_response(
        {
            "ok": ok,
            "message": (
                t.get("msg_delete_request_created")
                if ok
                else t.get("msg_delete_request_skipped_not_friend")
            )
            or ("删除请求已创建" if ok else "当前不是好友关系，无法创建删除请求"),
        }
    )


@router.post("/management/friendships/{request_id}/cancel")
async def post_friendship_cancel(request_id: int):
    """取消好友请求。"""
    ok = cancel_pending_request(request_id=request_id)
    _, t = get_current_i18n()
    return json_response(
        {
            "ok": ok,
            "message": (
                t.get("msg_request_cancelled") if ok else t.get("msg_request_cancel_failed")
            )
            or ("请求记录已删除" if ok else "仅允许删除未执行的申请记录"),
        }
    )
