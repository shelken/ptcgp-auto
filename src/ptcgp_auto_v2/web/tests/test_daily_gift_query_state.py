# -*- coding: utf-8 -*-
"""每日送卡查询状态回归测试。"""

from __future__ import annotations

from datetime import datetime, timedelta

import pytest
from sqlalchemy.pool import StaticPool
from sqlmodel import SQLModel, Session, create_engine

import ptcgp_auto_v2.db.models  # noqa: F401
from ptcgp_auto_v2.db.models.account import Account
from ptcgp_auto_v2.db.models.account_gift_pair import AccountGiftPair
from ptcgp_auto_v2.db.models.account_gift_record import AccountGiftRecord
from ptcgp_auto_v2.web.services.daily_gift_service import build_daily_gift_context


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


def _seed_daily_gift_rows(session: Session) -> None:
    """准备最小每日送卡样本。"""
    base = datetime(2026, 4, 14, 12, 0, 0)
    session.add_all(
        [
            Account(id=1, game_id="game-ash", nickname="Ash", friend_id="1111000011110000"),
            Account(id=2, game_id="game-misty", nickname="Misty", friend_id="2222000022220000"),
            Account(id=3, game_id="game-brock", nickname="Brock", friend_id="3333000033330000"),
            Account(id=4, game_id="game-serena", nickname="Serena", friend_id="4444000044440000"),
        ]
    )
    session.add_all(
        [
            AccountGiftPair(account_id=1, target_account_id=2, target_friend_id="2222000022220000"),
            AccountGiftPair(account_id=2, target_account_id=1, target_friend_id="1111000011110000"),
            AccountGiftPair(account_id=3, target_account_id=4, target_friend_id="4444000044440000"),
            AccountGiftPair(account_id=4, target_account_id=3, target_friend_id="3333000033330000"),
        ]
    )
    session.add_all(
        [
            AccountGiftRecord(
                id=1,
                account_id=1,
                target_account_id=2,
                target_friend_id="2222000022220000",
                status="success",
                biz_date_local="2026-04-14",
                updated_at=base,
            ),
            AccountGiftRecord(
                id=2,
                account_id=2,
                target_account_id=1,
                target_friend_id="1111000011110000",
                status="failed",
                biz_date_local="2026-04-14",
                updated_at=base + timedelta(minutes=10),
            ),
        ]
    )
    session.commit()


def test_build_daily_gift_context_returns_normalized_sort_state(session: Session) -> None:
    _seed_daily_gift_rows(session)

    context = build_daily_gift_context(
        session=session,
        biz_date_local="2026-04-14",
        sort_by="unknown_field",
        sort_order="sideways",
        page=0,
        page_size=10,
    )

    assert context["sort_by"] == "updated_at"
    assert context["sort_order"] == "desc"
    assert [row["id"] for row in context["records"]] == [2, 1]


def test_build_daily_gift_context_keeps_record_and_pair_pagination_independent(
    session: Session,
) -> None:
    _seed_daily_gift_rows(session)

    context = build_daily_gift_context(
        session=session,
        biz_date_local="2026-04-14",
        account_id=None,
        sort_by="updated_at",
        sort_order="desc",
        page=0,
        page_size=1,
        pair_page=1,
        pair_page_size=1,
    )

    assert [row["id"] for row in context["records"]] == [2]
    assert context["records_total"] == 2
    assert context["page"] == 0
    assert context["page_size"] == 1
    assert context["has_prev"] is False
    assert context["has_next"] is True

    assert len(context["pair_send_status_rows"]) == 1
    assert context["pair_total"] == 2
    assert context["pair_page"] == 1
    assert context["pair_page_size"] == 1
    assert context["pair_has_prev"] is True
    assert context["pair_has_next"] is False
    assert context["pair_send_status_rows"][0]["left_account_id"] == 3
    assert context["pair_send_status_rows"][0]["right_account_id"] == 4
