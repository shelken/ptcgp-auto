# -*- coding: utf-8 -*-

from datetime import datetime, timedelta

from sqlmodel import Session

from ptcgp_auto_v2.db.models import Account, AccountFriendRequest, AccountFriendship
from ptcgp_auto_v2.web.queries.friendship_queries import (
    list_friend_requests,
    list_friendships,
)


def test_list_friend_requests_supports_q_sort_and_pagination(session: Session):
    """好友请求应支持搜索、排序与分页。"""
    account_a = Account(
        game_id="fr_qs_a", friend_id="3000000000000001", nickname="Alpha"
    )
    account_b = Account(
        game_id="fr_qs_b", friend_id="3000000000000002", nickname="Bravo"
    )
    session.add(account_a)
    session.add(account_b)
    session.commit()
    session.refresh(account_a)
    session.refresh(account_b)

    base = datetime.now() - timedelta(minutes=10)
    rows = [
        AccountFriendRequest(
            from_account_id=account_a.id,
            to_account_id=account_b.id,
            to_friend_id="1000000000000001",
            request_type="add",
            status="sending",
            created_at=base,
            updated_at=base,
        ),
        AccountFriendRequest(
            from_account_id=account_a.id,
            to_account_id=account_b.id,
            to_friend_id="1000000000009999",
            request_type="add",
            status="sended",
            created_at=base + timedelta(minutes=1),
            updated_at=base + timedelta(minutes=1),
        ),
        AccountFriendRequest(
            from_account_id=account_b.id,
            to_account_id=account_a.id,
            to_friend_id="2000000000000002",
            request_type="delete",
            status="failed",
            created_at=base + timedelta(minutes=2),
            updated_at=base + timedelta(minutes=2),
        ),
    ]
    session.add_all(rows)
    session.commit()

    filtered, total = list_friend_requests(
        session=session,
        account_id=None,
        q="9999",
        sort_by="created_at",
        sort_order="desc",
        page=0,
        page_size=10,
    )
    assert total == 1
    assert len(filtered) == 1
    assert filtered[0].to_friend_id == "1000000000009999"

    paged, total_all = list_friend_requests(
        session=session,
        account_id=None,
        q="",
        sort_by="created_at",
        sort_order="asc",
        page=1,
        page_size=2,
    )
    assert total_all == 3
    assert len(paged) == 1
    assert paged[0].to_friend_id == "2000000000000002"


def test_list_friendships_supports_q_sort_and_pagination(session: Session):
    """好友关系应支持搜索、排序与分页。"""
    account_a = Account(
        game_id="fs_qs_a", friend_id="4000000000000001", nickname="Alice"
    )
    account_b = Account(game_id="fs_qs_b", friend_id="4000000000000002", nickname="Bob")
    session.add(account_a)
    session.add(account_b)
    session.commit()
    session.refresh(account_a)
    session.refresh(account_b)

    base = datetime.now() - timedelta(minutes=10)
    rows = [
        AccountFriendship(
            account_id=account_a.id,
            friend_id="9000000000000001",
            friend_account_id=account_b.id,
            created_at=base,
        ),
        AccountFriendship(
            account_id=account_a.id,
            friend_id="9000000000000002",
            friend_account_id=account_b.id,
            created_at=base + timedelta(minutes=1),
        ),
        AccountFriendship(
            account_id=account_b.id,
            friend_id="8000000000000001",
            friend_account_id=account_a.id,
            created_at=base + timedelta(minutes=2),
        ),
    ]
    session.add_all(rows)
    session.commit()

    filtered, total = list_friendships(
        session=session,
        account_id=None,
        q="9000000000000002",
        sort_by="created_at",
        sort_order="asc",
        page=0,
        page_size=10,
    )
    assert total == 1
    assert len(filtered) == 1
    assert filtered[0].friend_id == "9000000000000002"

    paged, total_all = list_friendships(
        session=session,
        account_id=None,
        q="",
        sort_by="created_at",
        sort_order="asc",
        page=1,
        page_size=2,
    )
    assert total_all == 3
    assert len(paged) == 1
    assert paged[0].friend_id == "8000000000000001"
