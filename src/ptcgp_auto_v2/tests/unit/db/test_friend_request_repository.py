# -*- coding: utf-8 -*-
"""FriendRequestRepository 行为测试。"""

from datetime import datetime, timedelta

from sqlmodel import Session, SQLModel, create_engine

from ptcgp_auto_v2.db.models import AccountFriendRequest
from ptcgp_auto_v2.db.repositories.friend_request_repository import FriendRequestRepository


def _request(
    *,
    from_account_id: int,
    to_account_id: int | None,
    request_type: str,
    status: str,
    minutes: int,
) -> AccountFriendRequest:
    created_at = datetime(2026, 1, 1, 12, 0, 0) + timedelta(minutes=minutes)
    return AccountFriendRequest(
        from_account_id=from_account_id,
        to_account_id=to_account_id,
        to_friend_id=f"friend-{minutes}",
        request_type=request_type,
        status=status,
        created_at=created_at,
        updated_at=created_at,
    )


def test_list_manage_friendship_pending_data_returns_only_pending_categories(tmp_path):
    """当前账号 pending 快照只包含 manage_friendship 需要处理的 5 类请求。"""
    db_path = tmp_path / "friend_requests.db"
    engine = create_engine(f"sqlite:///{db_path}")
    SQLModel.metadata.create_all(engine)

    included = [
        _request(from_account_id=1, to_account_id=2, request_type="add", status="sending", minutes=1),
        _request(from_account_id=2, to_account_id=1, request_type="add", status="sended", minutes=2),
        _request(from_account_id=1, to_account_id=None, request_type="add", status="sended", minutes=3),
        _request(from_account_id=1, to_account_id=2, request_type="add", status="canceling", minutes=4),
        _request(from_account_id=1, to_account_id=2, request_type="delete", status="deleting", minutes=5),
    ]
    excluded = [
        _request(from_account_id=1, to_account_id=2, request_type="delete", status="sended", minutes=6),
        _request(from_account_id=2, to_account_id=1, request_type="delete", status="sended", minutes=7),
        _request(from_account_id=1, to_account_id=None, request_type="add", status="completed", minutes=8),
        _request(from_account_id=3, to_account_id=4, request_type="add", status="sending", minutes=9),
    ]

    with Session(engine) as session:
        session.add_all([*included, *excluded])
        session.commit()

    with Session(engine) as session:
        rows = FriendRequestRepository(session).list_manage_friendship_pending_data(1)

    assert [(row.from_account_id, row.to_account_id, row.request_type, row.status) for row in rows] == [
        (1, 2, "add", "sending"),
        (2, 1, "add", "sended"),
        (1, None, "add", "sended"),
        (1, 2, "add", "canceling"),
        (1, 2, "delete", "deleting"),
    ]
