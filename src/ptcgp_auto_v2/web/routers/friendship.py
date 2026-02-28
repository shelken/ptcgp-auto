import json

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import HTMLResponse
from sqlmodel import Session

from ptcgp_auto_v2.db.engine import get_fastapi_session
from ptcgp_auto_v2.db.models import Account
from ptcgp_auto_v2.web.services.friendship_service import (
    build_friendship_context,
    cancel_pending_request,
    create_add_request,
    create_delete_request,
)
from ptcgp_auto_v2.web.utils.form_utils import parse_optional_int, safe_get_string
from ptcgp_auto_v2.web.utils.response_utils import render_template


router = APIRouter()


@router.get("/management/friendships", response_class=HTMLResponse)
async def get_management_friendships(
    request: Request,
    account_id: str | None = Query(default=None),
    from_account_id: str | None = Query(default=None),
    q: str = Query(default=""),
    sort_by: str = Query(default="created_at"),
    sort_order: str = Query(default="desc"),
    page: int = Query(default=0),
    page_size: int = Query(default=10),
    session: Session = Depends(get_fastapi_session),
):
    """渲染好友关系管理页面。"""
    selected_account_id = parse_optional_int(account_id)
    selected_from_account_id = parse_optional_int(from_account_id)
    context = build_friendship_context(
        session=session,
        account_id=selected_account_id,
        from_account_id=selected_from_account_id,
        q=q,
        sort_by=sort_by,
        sort_order=sort_order,
        page=max(page, 0),
        page_size=min(max(page_size, 1), 100),
    )
    return render_template(request, "partials/friendship_list.html", context)


@router.post("/api/friendships/requests/add", response_class=HTMLResponse)
async def post_add_friend_request(
    request: Request,
    session: Session = Depends(get_fastapi_session),
):
    """从管理页面创建添加好友请求。"""
    form = await request.form()
    from_account_id = parse_optional_int(form.get("from_account_id"))
    to_account_id = parse_optional_int(form.get("to_account_id"))
    to_friend_id = safe_get_string(form, "to_friend_id") or ""
    selected_account_id = parse_optional_int(form.get("selected_account_id"))
    selected_from_account_id = (
        parse_optional_int(form.get("selected_from_account_id")) or from_account_id
    )
    q = safe_get_string(form, "q") or ""
    sort_by = safe_get_string(form, "sort_by") or "created_at"
    sort_order = safe_get_string(form, "sort_order") or "desc"
    page = parse_optional_int(form.get("page")) or 0
    page_size = parse_optional_int(form.get("page_size")) or 10

    # 系统内账号可不手动填写 friend_id，后端自动补全
    if not to_friend_id and to_account_id:
        target_account = session.get(Account, to_account_id)
        if target_account and target_account.friend_id:
            to_friend_id = target_account.friend_id

    if from_account_id and to_friend_id:
        create_ok = create_add_request(
            from_account_id=from_account_id,
            to_friend_id=to_friend_id,
            to_account_id=to_account_id,
        )
    else:
        create_ok = False

    response = await get_management_friendships(
        request=request,
        account_id=str(selected_account_id)
        if selected_account_id is not None
        else None,
        from_account_id=str(selected_from_account_id)
        if selected_from_account_id is not None
        else None,
        q=q,
        sort_by=sort_by,
        sort_order=sort_order,
        page=page,
        page_size=page_size,
        session=session,
    )

    context = build_friendship_context(session=session)
    t = context["t"]
    message = (
        t.get("msg_add_request_created")
        if create_ok
        else t.get("msg_add_request_skipped")
    ) or ("添加请求已创建" if create_ok else "无效或重复请求，未创建添加申请")
    response.headers["HX-Trigger"] = json.dumps(
        {"showToast": {"message": message}}, ensure_ascii=True
    )
    return response


@router.post("/api/friendships/requests/delete", response_class=HTMLResponse)
async def post_delete_friend_request(
    request: Request,
    session: Session = Depends(get_fastapi_session),
):
    """从管理页面创建删除好友请求。"""
    form = await request.form()
    from_account_id = parse_optional_int(form.get("from_account_id"))
    to_account_id = parse_optional_int(form.get("to_account_id"))
    friend_id = safe_get_string(form, "friend_id") or ""
    selected_account_id = parse_optional_int(form.get("selected_account_id"))
    selected_from_account_id = (
        parse_optional_int(form.get("selected_from_account_id")) or from_account_id
    )
    q = safe_get_string(form, "q") or ""
    sort_by = safe_get_string(form, "sort_by") or "created_at"
    sort_order = safe_get_string(form, "sort_order") or "desc"
    page = parse_optional_int(form.get("page")) or 0
    page_size = parse_optional_int(form.get("page_size")) or 10

    # 删除时可直接选择系统账号，后端自动补全 friend_id
    if not friend_id and to_account_id:
        target_account = session.get(Account, to_account_id)
        if target_account and target_account.friend_id:
            friend_id = target_account.friend_id

    if from_account_id and friend_id:
        create_ok = create_delete_request(
            from_account_id=from_account_id,
            friend_id=friend_id,
            to_account_id=to_account_id,
        )
    else:
        create_ok = False

    response = await get_management_friendships(
        request=request,
        account_id=str(selected_account_id)
        if selected_account_id is not None
        else None,
        from_account_id=str(selected_from_account_id)
        if selected_from_account_id is not None
        else None,
        q=q,
        sort_by=sort_by,
        sort_order=sort_order,
        page=page,
        page_size=page_size,
        session=session,
    )

    context = build_friendship_context(session=session)
    t = context["t"]
    message = (
        t.get("msg_delete_request_created")
        if create_ok
        else t.get("msg_delete_request_skipped_not_friend")
    ) or ("删除请求已创建" if create_ok else "当前不是好友关系，无法创建删除请求")
    response.headers["HX-Trigger"] = json.dumps(
        {"showToast": {"message": message}}, ensure_ascii=True
    )
    return response


@router.post(
    "/api/friendships/requests/{request_id}/cancel", response_class=HTMLResponse
)
async def post_cancel_friend_request(
    request_id: int,
    request: Request,
    selected_account_id: str | None = Query(default=None),
    selected_from_account_id: str | None = Query(default=None),
    q: str = Query(default=""),
    sort_by: str = Query(default="created_at"),
    sort_order: str = Query(default="desc"),
    page: int = Query(default=0),
    page_size: int = Query(default=10),
    session: Session = Depends(get_fastapi_session),
):
    """取消尚未执行的好友请求记录。"""
    cancelled = cancel_pending_request(request_id=request_id)
    response = await get_management_friendships(
        request=request,
        account_id=selected_account_id,
        from_account_id=selected_from_account_id,
        q=q,
        sort_by=sort_by,
        sort_order=sort_order,
        page=page,
        page_size=page_size,
        session=session,
    )

    context = build_friendship_context(session=session)
    t = context["t"]
    message = (
        t.get("msg_request_cancelled")
        if cancelled
        else t.get("msg_request_cancel_failed")
    ) or ("请求记录已删除" if cancelled else "仅允许删除未执行的申请记录")
    response.headers["HX-Trigger"] = json.dumps(
        {"showToast": {"message": message}}, ensure_ascii=True
    )
    return response
