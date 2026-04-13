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
from ptcgp_auto_v2.web.utils.filter_utils import normalize_page, normalize_page_size
from ptcgp_auto_v2.web.utils.serialization import serialize_account


def build_friendship_context(
    session: Session,
    account_id: int | None = None,
    from_account_id: int | None = None,
    q: str = "",
    sort_by: str = "created_at",
    sort_order: str = "desc",
    page: int = 0,
    page_size: int = 10,
    request_sort_by: str | None = None,
    request_sort_order: str | None = None,
    request_page: int | None = None,
    request_page_size: int | None = None,
    friendship_sort_by: str | None = None,
    friendship_sort_order: str | None = None,
    friendship_page: int | None = None,
    friendship_page_size: int | None = None,
) -> dict:
    """构建好友管理页面所需上下文数据。"""
    normalized_request_sort_by = request_sort_by or sort_by
    normalized_request_sort_order = request_sort_order or sort_order
    normalized_page = normalize_page(page)
    normalized_page_size = normalize_page_size(page_size)
    normalized_request_page = (
        normalized_page if request_page is None else normalize_page(request_page)
    )
    normalized_request_page_size = (
        normalized_page_size
        if request_page_size is None
        else normalize_page_size(request_page_size)
    )
    normalized_friendship_sort_by = friendship_sort_by or sort_by
    normalized_friendship_sort_order = friendship_sort_order or sort_order
    normalized_friendship_page = (
        normalized_page
        if friendship_page is None
        else normalize_page(friendship_page)
    )
    normalized_friendship_page_size = (
        normalized_page_size
        if friendship_page_size is None
        else normalize_page_size(friendship_page_size)
    )

    account_repo = AccountRepository(session)
    accounts = [serialize_account(account) for account in account_repo.get_all()]

    account_name_map: dict[int, str] = {}
    account_friend_id_map: dict[int, str] = {}
    for account in accounts:
        if account["id"] is None:
            continue
        account_name_map[account["id"]] = str(account["display_name"])
        account_friend_id_map[account["id"]] = str(account["friend_id"] or "-")

    request_result = list_friend_requests(
        session=session,
        account_id=account_id,
        from_account_id=from_account_id,
        q=q,
        sort_by=normalized_request_sort_by,
        sort_order=normalized_request_sort_order,
        page=normalized_request_page,
        page_size=normalized_request_page_size,
    )
    friendship_result = list_friendships(
        session=session,
        account_id=account_id,
        q=q,
        sort_by=normalized_friendship_sort_by,
        sort_order=normalized_friendship_sort_order,
        page=normalized_friendship_page,
        page_size=normalized_friendship_page_size,
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

    request_rows = [row.model_dump() for row in requests]
    friendship_rows = [row.model_dump() for row in friendships]

    return {
        "accounts": accounts,
        "requests": request_rows,
        "request_total": request_total,
        "request_sort_by": normalized_request_sort_by,
        "request_sort_order": normalized_request_sort_order,
        "request_page": normalized_request_page,
        "request_page_size": normalized_request_page_size,
        "request_has_prev": normalized_request_page > 0,
        "request_has_next": (
            (normalized_request_page + 1) * normalized_request_page_size < request_total
        ),
        "friendships": friendship_rows,
        "friendship_total": friendship_total,
        "friendship_sort_by": normalized_friendship_sort_by,
        "friendship_sort_order": normalized_friendship_sort_order,
        "friendship_page": normalized_friendship_page,
        "friendship_page_size": normalized_friendship_page_size,
        "friendship_has_prev": normalized_friendship_page > 0,
        "friendship_has_next": (
            (normalized_friendship_page + 1) * normalized_friendship_page_size
            < friendship_total
        ),
        "account_name_map": account_name_map,
        "account_friend_id_map": account_friend_id_map,
        "selected_account_id": account_id,
        "selected_from_account_id": from_account_id,
        "q": q,
        "sort_by": normalized_request_sort_by,
        "sort_order": normalized_request_sort_order,
        "page": normalized_request_page,
        "page_size": normalized_request_page_size,
        "has_prev": normalized_request_page > 0,
        "has_next": (
            (normalized_request_page + 1) * normalized_request_page_size
            < max(request_total, friendship_total)
        ),
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
