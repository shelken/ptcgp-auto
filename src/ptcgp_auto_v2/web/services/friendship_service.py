# -*- coding: utf-8 -*-
"""
好友关系管理页面服务。

提供好友请求列表、好友关系列表以及手动触发请求的能力。
"""

from sqlmodel import Session

from ptcgp_auto_v2.db.repositories import AccountRepository
from ptcgp_auto_v2.services.friendship_service import FriendshipService
from ptcgp_auto_v2.web.queries.friendship_queries import (
    list_friend_requests,
    list_friendships,
)
from ptcgp_auto_v2.web.utils.i18n import get_translations, normalize_lang


def build_friendship_context(
    session: Session,
    lang: str,
    account_id: int | None = None,
    from_account_id: int | None = None,
    q: str = "",
    sort_by: str = "created_at",
    sort_order: str = "desc",
    page: int = 0,
    page_size: int = 10,
) -> dict:
    """构建好友管理页面所需上下文数据。"""
    current_lang = normalize_lang(lang)
    t = get_translations(current_lang)
    account_repo = AccountRepository()
    accounts = account_repo.get_all()

    account_name_map: dict[int, str] = {}
    account_friend_id_map: dict[int, str] = {}
    for account in accounts:
        if account.id is None:
            continue
        account_name_map[account.id] = account.display_name
        account_friend_id_map[account.id] = account.friend_id or "-"

    request_result = list_friend_requests(
        session=session,
        account_id=account_id,
        q=q,
        sort_by=sort_by,
        sort_order=sort_order,
        page=page,
        page_size=page_size,
    )
    friendship_result = list_friendships(
        session=session,
        account_id=account_id,
        q=q,
        sort_by=sort_by,
        sort_order=sort_order,
        page=page,
        page_size=page_size,
    )

    if isinstance(request_result, tuple):
        requests, request_total = request_result
    else:
        requests = request_result
        request_total = len(requests)

    if isinstance(friendship_result, tuple):
        friendships, friendship_total = friendship_result
    else:
        friendships = friendship_result
        friendship_total = len(friendships)

    return {
        "accounts": accounts,
        "requests": requests,
        "request_total": request_total,
        "friendships": friendships,
        "friendship_total": friendship_total,
        "account_name_map": account_name_map,
        "account_friend_id_map": account_friend_id_map,
        "selected_account_id": account_id,
        "selected_from_account_id": from_account_id,
        "q": q,
        "sort_by": sort_by,
        "sort_order": sort_order,
        "page": page,
        "page_size": page_size,
        "has_prev": page > 0,
        "has_next": (page + 1) * page_size < max(request_total, friendship_total),
        "t": t,
        "current_lang": current_lang,
    }


def create_add_request(
    from_account_id: int,
    to_friend_id: str,
    to_account_id: int | None,
) -> bool:
    """创建添加好友请求并触发调度。"""
    request = FriendshipService.create_add_request(
        from_account_id=from_account_id,
        to_friend_id=to_friend_id,
        to_account_id=to_account_id,
    )
    return request is not None


def create_delete_request(
    from_account_id: int, friend_id: str, to_account_id: int | None = None
) -> bool:
    """创建删除好友请求并触发调度。"""
    request = FriendshipService.create_delete_request(
        account_id=from_account_id,
        friend_id=friend_id,
        to_account_id=to_account_id,
    )
    return request is not None


def cancel_pending_request(request_id: int) -> bool:
    """取消尚未执行的请求记录。"""
    return FriendshipService.cancel_request(request_id=request_id)
