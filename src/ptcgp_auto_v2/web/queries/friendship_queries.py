# -*- coding: utf-8 -*-
"""
好友关系查询模块。

封装好友请求与好友关系列表查询，供 Web 服务层复用。
"""

from sqlalchemy import String, cast, func, or_
from sqlmodel import Session, col, select

from ptcgp_auto_v2.db.models import AccountFriendRequest, AccountFriendship


def list_friend_requests(
    session: Session,
    account_id: int | None = None,
    limit: int = 100,
    q: str = "",
    sort_by: str = "created_at",
    sort_order: str = "desc",
    page: int | None = None,
    page_size: int | None = None,
) -> tuple[list[AccountFriendRequest], int] | list[AccountFriendRequest]:
    """按条件查询好友请求，兼容旧版全量和新版分页模式。"""
    statement = select(AccountFriendRequest)
    if account_id is not None:
        statement = statement.where(
            or_(
                col(AccountFriendRequest.from_account_id) == account_id,
                col(AccountFriendRequest.to_account_id) == account_id,
            )
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

    sort_mapping = {
        "created_at": col(AccountFriendRequest.created_at),
        "updated_at": col(AccountFriendRequest.updated_at),
        "from_account_id": col(AccountFriendRequest.from_account_id),
        "to_friend_id": col(AccountFriendRequest.to_friend_id),
        "status": col(AccountFriendRequest.status),
    }
    sort_column = sort_mapping.get(sort_by, col(AccountFriendRequest.created_at))
    sort_direction = "asc" if sort_order == "asc" else "desc"
    if sort_direction == "asc":
        statement = statement.order_by(sort_column.asc())
    else:
        statement = statement.order_by(sort_column.desc())

    if page is None or page_size is None:
        return list(session.exec(statement.limit(limit)).all())

    normalized_page = max(page, 0)
    normalized_page_size = min(max(page_size, 1), 100)
    total = int(
        session.exec(select(func.count()).select_from(statement.subquery())).one()
    )
    rows = list(
        session.exec(
            statement.offset(normalized_page * normalized_page_size).limit(
                normalized_page_size
            )
        ).all()
    )
    return rows, total


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

    sort_mapping = {
        "created_at": col(AccountFriendship.created_at),
        "account_id": col(AccountFriendship.account_id),
        "friend_id": col(AccountFriendship.friend_id),
    }
    sort_column = sort_mapping.get(sort_by, col(AccountFriendship.created_at))
    sort_direction = "asc" if sort_order == "asc" else "desc"
    if sort_direction == "asc":
        statement = statement.order_by(sort_column.asc())
    else:
        statement = statement.order_by(sort_column.desc())

    if page is None or page_size is None:
        return list(session.exec(statement.limit(limit)).all())

    normalized_page = max(page, 0)
    normalized_page_size = min(max(page_size, 1), 100)
    total = int(
        session.exec(select(func.count()).select_from(statement.subquery())).one()
    )
    rows = list(
        session.exec(
            statement.offset(normalized_page * normalized_page_size).limit(
                normalized_page_size
            )
        ).all()
    )
    return rows, total
