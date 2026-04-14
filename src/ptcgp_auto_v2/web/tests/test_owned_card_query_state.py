# -*- coding: utf-8 -*-
"""拥有卡牌服务层查询状态回归测试。"""

from __future__ import annotations

from datetime import datetime

import pytest
from sqlalchemy.pool import StaticPool
from sqlmodel import SQLModel, Session, create_engine

import ptcgp_auto_v2.db.models  # noqa: F401
from ptcgp_auto_v2.db.models.account import Account
from ptcgp_auto_v2.db.models.account_card import AccountCard
from ptcgp_auto_v2.db.models.account_stat import AccountStat
from ptcgp_auto_v2.db.models.card import Card
from ptcgp_auto_v2.web.services.owned_card_service import (
    build_owned_card_exchange_accounts_context,
    build_owned_cards_list_context,
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


def _seed_owned_cards_rows(session: Session) -> None:
    """准备拥有卡牌页最小样本。"""
    now = datetime(2026, 4, 14, 12, 0, 0)
    session.add_all(
        [
            Account(
                id=1,
                game_id="game-ash",
                nickname="Ash",
                friend_id="1111000011110000",
                updated_at=now,
            ),
            Account(
                id=2,
                game_id="game-misty",
                nickname="Misty",
                friend_id="2222000022220000",
                updated_at=now,
            ),
            Card(
                id=101,
                set_code="A1",
                number=1,
                name="Alpha",
                rarity="SR",
                image_url="alpha.png",
                type="pokemon",
                element="fire",
            ),
            Card(
                id=102,
                set_code="A1",
                number=2,
                name="Beta",
                rarity="AR",
                image_url="beta.png",
                type="trainer",
                element="water",
            ),
            AccountCard(account_id=1, card_id=101, count=2),
            AccountCard(account_id=2, card_id=101, count=1),
            AccountStat(account_id=1, exchange_points=120, pack_hourglass_count=8),
            AccountStat(account_id=2, exchange_points=20, pack_hourglass_count=3),
        ]
    )
    session.commit()


def test_build_owned_cards_list_context_returns_normalized_query_state(
    session: Session,
) -> None:
    _seed_owned_cards_rows(session)

    context = build_owned_cards_list_context(
        session=session,
        page=-3,
        page_size=999,
        account_id=" 1 ",
        rarity=[" SR "],
        card_type=[" pokemon "],
        set_code=[" A1 "],
        pack_name=[],
        element=[" fire "],
        sort_by="invalid_field",
        ownership_scope="invalid_scope",
    )

    assert [row["card"].id for row in context["items"]] == [101]
    assert context["sort_by"] == "acquired"
    assert context["page"] == 0
    assert context["page_size"] == 100
    assert context["ownership_scope"] == "owned"
    assert context["total"] == 1


def test_build_owned_card_exchange_accounts_context_returns_normalized_query_state(
    session: Session,
) -> None:
    _seed_owned_cards_rows(session)

    context = build_owned_card_exchange_accounts_context(
        session=session,
        card_id=101,
        page=-4,
        page_size=999,
        q=" ash ",
        sort_by="invalid_field",
        sort_order="sideways",
    )

    assert [row["account_id"] for row in context["accounts"]] == [1]
    assert context["q"] == "ash"
    assert context["sort_by"] == "account_id"
    assert context["sort_order"] == "asc"
    assert context["page"] == 0
    assert context["page_size"] == 50
    assert context["total"] == 1
    assert context["total_items"] == 1
