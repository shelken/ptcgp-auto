# -*- coding: utf-8 -*-
"""开包记录列表筛选回归测试。"""

from __future__ import annotations

from datetime import datetime

import pytest
from sqlalchemy.pool import StaticPool
from sqlmodel import SQLModel, Session, create_engine

import ptcgp_auto_v2.db.models  # noqa: F401
from ptcgp_auto_v2.db.models.account import Account
from ptcgp_auto_v2.db.models.account_pack_point import AccountPackPoint
from ptcgp_auto_v2.db.models.card import Card
from ptcgp_auto_v2.db.models.pack_card import PackCard
from ptcgp_auto_v2.db.models.pack_record import PackRecord, PackRecordType
from ptcgp_auto_v2.web.queries.record_queries import fetch_pack_points_map
from ptcgp_auto_v2.web.services.record_service import build_records_list_context


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


def _seed_records(session: Session) -> None:
    """准备开包记录页最小样本。"""
    now = datetime(2026, 4, 14, 12, 0, 0)
    session.add(Account(id=1, game_id="game-ash", nickname="Ash", friend_id="1111", updated_at=now))
    session.add_all(
        [
            Card(
                id=101,
                set_code="A1",
                number=1,
                name="Pikachu",
                rarity="SR",
                image_url="pikachu.png",
                type="pokemon",
                element="electric",
            ),
            Card(
                id=102,
                set_code="A2",
                number=2,
                name="Squirtle",
                rarity="AR",
                image_url="squirtle.png",
                type="pokemon",
                element="water",
            ),
        ]
    )
    session.add_all(
        [
            PackRecord(
                id=201,
                account_id=1,
                pack_type=PackRecordType.DAILY_FREE,
                pack_code="A1",
                pack_name="Pikachu",
                opened_at=now,
            ),
            PackRecord(
                id=202,
                account_id=1,
                pack_type=PackRecordType.DAILY_FREE,
                pack_code="A2",
                pack_name="Squirtle",
                opened_at=now.replace(hour=13),
            ),
            PackCard(pack_record_id=201, card_id=101, card_name="Pikachu", rarity="SR", position=1),
            PackCard(pack_record_id=202, card_id=102, card_name="Squirtle", rarity="AR", position=1),
        ]
    )
    session.commit()


def test_fetch_pack_points_map_only_returns_current_page_series(session: Session) -> None:
    now = datetime(2026, 4, 14, 12, 0, 0)
    session.add(Account(id=1, game_id="game-ash", nickname="Ash", friend_id="1111", updated_at=now))
    current_record = PackRecord(
        id=301,
        account_id=1,
        pack_type=PackRecordType.DAILY_FREE,
        pack_code="A1",
        opened_at=now,
    )
    session.add(current_record)
    session.add_all(
        [
            AccountPackPoint(account_id=1, series="A1", points=10, updated_at=now),
            AccountPackPoint(account_id=1, series="A2", points=999, updated_at=now),
        ]
    )
    session.commit()

    points_map = fetch_pack_points_map(session, [current_record])

    assert points_map == {(1, "A1"): 10}


def test_fetch_pack_points_map_uses_legacy_pack_type_series(session: Session) -> None:
    now = datetime(2026, 4, 14, 12, 0, 0)
    session.add(Account(id=1, game_id="game-ash", nickname="Ash", friend_id="1111", updated_at=now))
    current_record = PackRecord(
        id=302,
        account_id=1,
        pack_code=None,
        pack_type="A1/Pikachu",
        opened_at=now,
    )
    session.add(current_record)
    session.add(AccountPackPoint(account_id=1, series="A1", points=10, updated_at=now))
    session.commit()

    points_map = fetch_pack_points_map(session, [current_record])

    assert points_map == {(1, "A1"): 10}


def test_build_records_list_context_filters_by_set_code(session: Session) -> None:
    _seed_records(session)

    context = build_records_list_context(session=session, set_code=["A1"])

    assert [item["series"] for item in context["items"]] == ["A1"]
    assert [card["display_name"] for card in context["items"][0]["cards"]] == ["Pikachu"]


def test_build_records_list_context_filters_by_card_name_query(session: Session) -> None:
    _seed_records(session)

    context = build_records_list_context(session=session, card_name_query="squ")

    assert [item["series"] for item in context["items"]] == ["A2"]
    assert [card["display_name"] for card in context["items"][0]["cards"]] == ["Squirtle"]


def test_build_records_list_context_orders_same_time_ten_pack_batches_by_max_id(
    session: Session,
) -> None:
    opened_at = datetime(2026, 4, 14, 12, 0, 0)
    session.add(Account(id=1, game_id="game-ash", nickname="Ash", friend_id="1111", updated_at=opened_at))
    session.add_all(
        [
            PackRecord(
                id=301,
                account_id=1,
                pack_type=PackRecordType.TEN_PACK,
                batch_id="batch-a",
                batch_index=1,
                opened_at=opened_at,
            ),
            PackRecord(
                id=302,
                account_id=1,
                pack_type=PackRecordType.TEN_PACK,
                batch_id="batch-a",
                batch_index=2,
                opened_at=opened_at,
            ),
            PackRecord(
                id=401,
                account_id=1,
                pack_type=PackRecordType.TEN_PACK,
                batch_id="batch-b",
                batch_index=1,
                opened_at=opened_at,
            ),
            PackRecord(
                id=402,
                account_id=1,
                pack_type=PackRecordType.TEN_PACK,
                batch_id="batch-b",
                batch_index=2,
                opened_at=opened_at,
            ),
        ]
    )
    session.commit()

    first_page = build_records_list_context(session=session, page=0, page_size=1)
    second_page = build_records_list_context(session=session, page=1, page_size=1)

    assert [item["batch_id"] for item in first_page["items"]] == ["batch-b"]
    assert [item["batch_id"] for item in second_page["items"]] == ["batch-a"]


def test_build_records_list_context_keeps_same_batch_id_separate_by_account(
    session: Session,
) -> None:
    opened_at = datetime(2026, 4, 14, 12, 0, 0)
    session.add_all(
        [
            Account(id=1, game_id="game-ash", nickname="Ash", friend_id="1111", updated_at=opened_at),
            Account(id=2, game_id="game-misty", nickname="Misty", friend_id="2222", updated_at=opened_at),
        ]
    )
    session.add_all(
        [
            PackRecord(
                id=501,
                account_id=1,
                pack_type=PackRecordType.TEN_PACK,
                batch_id="shared-batch",
                batch_index=1,
                opened_at=opened_at,
            ),
            PackRecord(
                id=502,
                account_id=1,
                pack_type=PackRecordType.TEN_PACK,
                batch_id="shared-batch",
                batch_index=2,
                opened_at=opened_at,
            ),
            PackRecord(
                id=601,
                account_id=2,
                pack_type=PackRecordType.TEN_PACK,
                batch_id="shared-batch",
                batch_index=1,
                opened_at=opened_at,
            ),
            PackRecord(
                id=602,
                account_id=2,
                pack_type=PackRecordType.TEN_PACK,
                batch_id="shared-batch",
                batch_index=2,
                opened_at=opened_at,
            ),
        ]
    )
    session.commit()

    context = build_records_list_context(session=session, page=0, page_size=10)

    assert [(item["record"].account_id, item["batch_id"]) for item in context["items"]] == [
        (2, "shared-batch"),
        (1, "shared-batch"),
    ]
    assert [item["account_name"] for item in context["items"]] == ["Misty", "Ash"]
    assert [item["batch_key"] for item in context["items"]] == ["2:shared-batch", "1:shared-batch"]
