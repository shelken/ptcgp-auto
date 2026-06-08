# -*- coding: utf-8 -*-
"""
好友关系查询模块。

封装好友请求与好友关系列表查询，供 Web 服务层复用。
"""

from sqlalchemy import String, cast, or_
from sqlmodel import Session, col, select

from ptcgp_auto_v2.db.models import AccountFriendRequest, AccountFriendship
from ptcgp_auto_v2.web.queries._query_helpers import (
    apply_sort,
    fetch_rows_with_optional_pagination,
    normalize_sort_params,
    resolve_sort_column,
)


FRIEND_REQUEST_SORT_FIELDS = {
    "created_at": col(AccountFriendRequest.created_at),
    "updated_at": col(AccountFriendRequest.updated_at),
    "from_account_id": col(AccountFriendRequest.from_account_id),
    "to_friend_id": col(AccountFriendRequest.to_friend_id),
    "status": col(AccountFriendRequest.status),
}

FRIENDSHIP_SORT_FIELDS = {
    "created_at": col(AccountFriendship.created_at),
    "account_id": col(AccountFriendship.account_id),
    "friend_id": col(AccountFriendship.friend_id),
}


def _build_friend_requests_statement(
    *,
    account_id: int | None,
    from_account_id: int | None,
    q: str,
    sort_by: str,
    sort_order: str,
):
    """构建好友请求查询语句。"""
    statement = select(AccountFriendRequest)
    if account_id is not None:
        statement = statement.where(
            or_(
                col(AccountFriendRequest.from_account_id) == account_id,
                col(AccountFriendRequest.to_account_id) == account_id,
            )
        )
    if from_account_id is not None:
        statement = statement.where(
            col(AccountFriendRequest.from_account_id) == from_account_id
        )

    q_text = q.strip()
    if q_text:
        statement = statement.where(
            or_(
                col(AccountFriendRequest.to_friend_id).ilike(f"%{q_text}%"),
                cast(col(AccountFriendRequest.from_account_id), String).ilike(
                    f"%{q_text}%"
                ),
                cast(col(AccountFriendRequest.to_account_id), String).ilike(
                    f"%{q_text}%"
                ),
            )
        )

    normalized_sort_by, normalized_sort_order = normalize_sort_params(
        sort_by=sort_by,
        sort_order=sort_order,
        allowed_fields=FRIEND_REQUEST_SORT_FIELDS,
        default_field="created_at",
    )
    sort_column = resolve_sort_column(
        sort_by=normalized_sort_by,
        fields=FRIEND_REQUEST_SORT_FIELDS,
        default_field="created_at",
    )
    return apply_sort(
        statement,
        sort_column=sort_column,
        sort_order=normalized_sort_order,
        tie_breaker_column=col(AccountFriendRequest.id),
    )


def _build_friendships_statement(
    *,
    account_id: int | None,
    q: str,
    sort_by: str,
    sort_order: str,
):
    """构建好友关系列表查询语句。"""
    statement = select(AccountFriendship)
    if account_id is not None:
        statement = statement.where(AccountFriendship.account_id == account_id)

    q_text = q.strip()
    if q_text:
        statement = statement.where(
            or_(
                col(AccountFriendship.friend_id).ilike(f"%{q_text}%"),
                cast(col(AccountFriendship.account_id), String).ilike(f"%{q_text}%"),
                cast(col(AccountFriendship.friend_account_id), String).ilike(
                    f"%{q_text}%"
                ),
            )
        )

    normalized_sort_by, normalized_sort_order = normalize_sort_params(
        sort_by=sort_by,
        sort_order=sort_order,
        allowed_fields=FRIENDSHIP_SORT_FIELDS,
        default_field="created_at",
    )
    sort_column = resolve_sort_column(
        sort_by=normalized_sort_by,
        fields=FRIENDSHIP_SORT_FIELDS,
        default_field="created_at",
    )
    return apply_sort(
        statement,
        sort_column=sort_column,
        sort_order=normalized_sort_order,
        tie_breaker_column=col(AccountFriendship.id),
    )


def list_friend_requests(
    session: Session,
    account_id: int | None = None,
    from_account_id: int | None = None,
    limit: int = 100,
    q: str = "",
    sort_by: str = "created_at",
    sort_order: str = "desc",
    page: int | None = None,
    page_size: int | None = None,
) -> tuple[list[AccountFriendRequest], int] | list[AccountFriendRequest]:
    """按条件查询好友请求，兼容旧版全量和新版分页模式。"""
    statement = _build_friend_requests_statement(
        account_id=account_id,
        from_account_id=from_account_id,
        q=q,
        sort_by=sort_by,
        sort_order=sort_order,
    )

    return fetch_rows_with_optional_pagination(
        session=session,
        statement=statement,
        page=page,
        page_size=page_size,
        full_limit=limit,
        max_page_size=100,
    )


def list_friendships(
    session: Session,
    account_id: int | None = None,
    limit: int = 100,
    q: str = "",
    sort_by: str = "created_at",
    sort_order: str = "desc",
    page: int | None = None,
    page_size: int | None = None,
) -> tuple[list[AccountFriendship], int] | list[AccountFriendship]:
    """按条件查询好友关系，兼容旧版全量和新版分页模式。"""
    statement = _build_friendships_statement(
        account_id=account_id,
        q=q,
        sort_by=sort_by,
        sort_order=sort_order,
    )

    return fetch_rows_with_optional_pagination(
        session=session,
        statement=statement,
        page=page,
        page_size=page_size,
        full_limit=limit,
        max_page_size=100,
    )
