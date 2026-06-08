# -*- coding: utf-8 -*-
"""好友管理查询回归测试。"""

from __future__ import annotations

from datetime import datetime

import pytest
from sqlalchemy.pool import StaticPool
from sqlmodel import SQLModel, Session, create_engine

import ptcgp_auto_v2.db.models  # noqa: F401
from ptcgp_auto_v2.db.models.account import Account
from ptcgp_auto_v2.db.models.account_friend_request import AccountFriendRequest
from ptcgp_auto_v2.db.models.account_friendship import AccountFriendship
from ptcgp_auto_v2.web.services.friendship_service import build_friendship_context


@pytest.fixture
def session() -> Session:
    """为每个用例准备独立内存数据库。"""
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)

    with Session(engine) as session:
        yield session

    engine.dispose()


def _seed_friendship_rows(session: Session) -> None:
    """准备最小好友请求和好友关系样本。"""
    now = datetime.now()
    session.add_all(
        [
            Account(id=1, game_id="game-ash", nickname="Ash", friend_id="1111000011110000"),
            Account(id=2, game_id="game-misty", nickname="Misty", friend_id="2222000022220000"),
            Account(id=3, game_id="game-brock", nickname="Brock", friend_id="3333000033330000"),
            Account(id=4, game_id="game-gary", nickname="Gary", friend_id="4444000044440000"),
        ]
    )
    session.add_all(
        [
            AccountFriendRequest(
                id=1,
                from_account_id=1,
                to_account_id=2,
                to_friend_id="2222000022220000",
                request_type="add",
                status="sending",
                created_at=now,
                updated_at=now,
            ),
            AccountFriendRequest(
                id=2,
                from_account_id=3,
                to_account_id=4,
                to_friend_id="4444000044440000",
                request_type="add",
                status="sending",
                created_at=now,
                updated_at=now,
            ),
            AccountFriendship(
                id=1,
                account_id=1,
                friend_id="2222000022220000",
                friend_account_id=2,
                created_at=now,
            ),
            AccountFriendship(
                id=2,
                account_id=3,
                friend_id="4444000044440000",
                friend_account_id=4,
                created_at=now,
            ),
        ]
    )
    session.commit()


def test_build_friendship_context_applies_from_account_filter(session: Session) -> None:
    _seed_friendship_rows(session)

    context = build_friendship_context(
        session=session,
        from_account_id=1,
        q="",
        sort_by="created_at",
        sort_order="desc",
        page=0,
        page_size=20,
    )

    assert [row["id"] for row in context["requests"]] == [1]
    assert context["request_total"] == 1
    assert [row["id"] for row in context["friendships"]] == [2, 1]


def test_build_friendship_context_supports_independent_request_and_friendship_list_state(
    session: Session,
) -> None:
    _seed_friendship_rows(session)

    context = build_friendship_context(
        session=session,
        q="",
        request_sort_by="from_account_id",
        request_sort_order="desc",
        request_page=0,
        request_page_size=1,
        friendship_sort_by="account_id",
        friendship_sort_order="desc",
        friendship_page=0,
        friendship_page_size=1,
    )

    assert [row["id"] for row in context["requests"]] == [2]
    assert context["request_total"] == 2
    assert context["request_page"] == 0
    assert context["request_page_size"] == 1
    assert context["request_has_next"] is True

    assert [row["id"] for row in context["friendships"]] == [2]
    assert context["friendship_total"] == 2
    assert context["friendship_page"] == 0
    assert context["friendship_page_size"] == 1
    assert context["friendship_has_next"] is True


def test_build_friendship_context_normalizes_shared_and_split_pagination_state(
    session: Session,
) -> None:
    _seed_friendship_rows(session)

    context = build_friendship_context(
        session=session,
        q="",
        page=-3,
        page_size=999,
        request_page=-9,
        friendship_page_size=999,
    )

    assert context["page"] == 0
    assert context["page_size"] == 100
    assert context["request_page"] == 0
    assert context["request_page_size"] == 100
    assert context["friendship_page"] == 0
    assert context["friendship_page_size"] == 100
