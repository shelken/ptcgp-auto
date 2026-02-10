# -*- coding: utf-8 -*-

from datetime import datetime, timedelta

from sqlmodel import Session

from ptcgp_auto_v2.db.models import Account, AccountFriendRequest, AccountFriendship
from ptcgp_auto_v2.web.queries.friendship_queries import (
    list_friend_requests,
    list_friendships,
)


def test_list_friend_requests_supports_filter_and_sort(session: Session):
    """应按创建时间倒序返回，并支持按发起账号过滤。"""
    account_a = Account(game_id="acc_a")
    account_b = Account(game_id="acc_b")
    session.add(account_a)
    session.add(account_b)
    session.commit()
    session.refresh(account_a)
    session.refresh(account_b)

    older = AccountFriendRequest(
        from_account_id=account_a.id,
        to_friend_id="1111222233334444",
        request_type="add",
        status="sending",
        created_at=datetime.now() - timedelta(minutes=2),
        updated_at=datetime.now() - timedelta(minutes=2),
    )
    newer = AccountFriendRequest(
        from_account_id=account_a.id,
        to_friend_id="5555666677778888",
        request_type="add",
        status="sended",
        created_at=datetime.now() - timedelta(minutes=1),
        updated_at=datetime.now() - timedelta(minutes=1),
    )
    other = AccountFriendRequest(
        from_account_id=account_b.id,
        to_friend_id="9999000011112222",
        request_type="delete",
        status="deleting",
        created_at=datetime.now(),
        updated_at=datetime.now(),
    )
    session.add(older)
    session.add(newer)
    session.add(other)
    session.commit()

    filtered_rows = list_friend_requests(session=session, account_id=account_a.id)
    assert [row.to_friend_id for row in filtered_rows] == [
        "5555666677778888",
        "1111222233334444",
    ]

    all_rows = list_friend_requests(session=session)
    assert [row.to_friend_id for row in all_rows] == [
        "9999000011112222",
        "5555666677778888",
        "1111222233334444",
    ]


def test_list_friendships_supports_account_filter_and_sort(session: Session):
    """应按创建时间倒序返回，并支持按账号过滤。"""
    account_a = Account(game_id="acc_filter_a")
    account_b = Account(game_id="acc_filter_b")
    session.add(account_a)
    session.add(account_b)
    session.commit()
    session.refresh(account_a)
    session.refresh(account_b)

    row_1 = AccountFriendship(
        account_id=account_a.id,
        friend_id="1234000012340000",
        created_at=datetime.now() - timedelta(minutes=2),
    )
    row_2 = AccountFriendship(
        account_id=account_a.id,
        friend_id="1234000012341111",
        created_at=datetime.now() - timedelta(minutes=1),
    )
    row_3 = AccountFriendship(
        account_id=account_b.id,
        friend_id="1234000012342222",
        created_at=datetime.now(),
    )
    session.add(row_1)
    session.add(row_2)
    session.add(row_3)
    session.commit()

    filtered_rows = list_friendships(session=session, account_id=account_a.id)
    assert [row.friend_id for row in filtered_rows] == [
        "1234000012341111",
        "1234000012340000",
    ]

    all_rows = list_friendships(session=session)
    assert [row.friend_id for row in all_rows] == [
        "1234000012342222",
        "1234000012341111",
        "1234000012340000",
    ]


def test_list_friend_requests_filter_matches_sender_or_receiver(session: Session):
    """账号筛选应命中发起方或接收方，避免系统账号视角看不到记录。"""
    account_a = Account(game_id="acc_sender")
    account_b = Account(game_id="acc_receiver")
    session.add(account_a)
    session.add(account_b)
    session.commit()
    session.refresh(account_a)
    session.refresh(account_b)

    row = AccountFriendRequest(
        from_account_id=account_a.id,
        to_account_id=account_b.id,
        to_friend_id="8888777766665555",
        request_type="add",
        status="sending",
        created_at=datetime.now(),
        updated_at=datetime.now(),
    )
    session.add(row)
    session.commit()

    rows_from_sender = list_friend_requests(session=session, account_id=account_a.id)
    assert len(rows_from_sender) == 1

    # 当前实现如果只按 from_account_id 过滤，这里会拿不到结果（应先红灯）
    rows_from_receiver = list_friend_requests(session=session, account_id=account_b.id)
    assert len(rows_from_receiver) == 1
