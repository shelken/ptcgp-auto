# -*- coding: utf-8 -*-
"""
好友关系查询模块。

封装好友请求与好友关系列表查询，供 Web 服务层复用。
"""

from sqlalchemy import or_
from sqlmodel import Session, select

from ptcgp_auto_v2.db.models import AccountFriendRequest, AccountFriendship


def list_friend_requests(
    session: Session,
    account_id: int | None = None,
    limit: int = 100,
) -> list[AccountFriendRequest]:
    """按创建时间倒序查询好友请求，支持按关联账号过滤。"""
    statement = select(AccountFriendRequest)
    if account_id is not None:
        statement = statement.where(
            or_(
                AccountFriendRequest.from_account_id == account_id,
                AccountFriendRequest.to_account_id == account_id,
            )
        )
    statement = statement.order_by(AccountFriendRequest.created_at.desc()).limit(limit)
    return list(session.exec(statement).all())


def list_friendships(
    session: Session,
    account_id: int | None = None,
    limit: int = 100,
) -> list[AccountFriendship]:
    """按创建时间倒序查询好友关系，支持按账号过滤。"""
    statement = select(AccountFriendship)
    if account_id is not None:
        statement = statement.where(AccountFriendship.account_id == account_id)
    statement = statement.order_by(AccountFriendship.created_at.desc()).limit(limit)
    return list(session.exec(statement).all())
