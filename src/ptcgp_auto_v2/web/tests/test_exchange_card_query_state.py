# -*- coding: utf-8 -*-
"""交换记录查询状态回归测试。"""

from __future__ import annotations

from datetime import datetime, timedelta

import pytest
from sqlalchemy.pool import StaticPool
from sqlmodel import SQLModel, Session, create_engine

import ptcgp_auto_v2.db.models  # noqa: F401
from ptcgp_auto_v2.db.models.exchange_card_request import ExchangeCardRequest
from ptcgp_auto_v2.web.services.exchange_card_service import (
    build_exchange_card_context,
)


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


def _seed_exchange_rows(session: Session) -> None:
    """准备最小交换请求样本。"""
    base = datetime(2026, 4, 14, 12, 0, 0)
    session.add_all(
        [
            ExchangeCardRequest(
                id=1,
                from_account_id=1,
                to_account_id=2,
                to_friend_id="1111000011110000",
                target_card_id=101,
                target_card_rarity="SR",
                status="sending",
                created_at=base,
                updated_at=base,
            ),
            ExchangeCardRequest(
                id=2,
                from_account_id=3,
                to_account_id=4,
                to_friend_id="2222000022220000",
                target_card_id=202,
                target_card_rarity="AR",
                status="completed",
                created_at=base + timedelta(minutes=5),
                updated_at=base + timedelta(minutes=5),
            ),
        ]
    )
    session.commit()


def test_build_exchange_card_context_returns_normalized_query_state(
    session: Session,
) -> None:
    _seed_exchange_rows(session)

    context = build_exchange_card_context(
        session=session,
        sort_by="unknown_field",
        sort_order="sideways",
        page=-3,
        page_size=999,
    )

    assert [row["id"] for row in context["requests"]] == [2, 1]
    assert context["sort_by"] == "created_at"
    assert context["sort_order"] == "desc"
    assert context["page"] == 0
    assert context["page_size"] == 100
