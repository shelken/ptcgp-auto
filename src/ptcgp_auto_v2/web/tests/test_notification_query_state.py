# -*- coding: utf-8 -*-
"""通知列表查询状态回归测试。"""

from __future__ import annotations

from datetime import datetime, timedelta

import pytest
from sqlalchemy.pool import StaticPool
from sqlmodel import SQLModel, Session, create_engine

import ptcgp_auto_v2.db.models  # noqa: F401
from ptcgp_auto_v2.db.models.account import Account
from ptcgp_auto_v2.db.models.card import Card, CardPack, CardSet, Pack
from ptcgp_auto_v2.db.models.notification import Notification
from ptcgp_auto_v2.web.services.notification_service import (
    build_notification_card_selector_context,
    build_notifications_context,
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


def _seed_notifications(session: Session) -> None:
    """准备主通知列表最小样本。"""
    base = datetime(2026, 4, 14, 12, 0, 0)
    session.add_all(
        [
            Account(id=1, game_id="game-ash", nickname="Ash", friend_id="1111000011110000"),
            Account(id=2, game_id="game-misty", nickname="Misty", friend_id="2222000022220000"),
            Notification(
                id=1,
                scene="system_warning",
                title="Alpha",
                content="first message",
                related_account_id=1,
                is_read=False,
                created_at=base,
            ),
            Notification(
                id=2,
                scene="task_status",
                title="Beta",
                content="match target",
                related_account_id=2,
                is_read=True,
                created_at=base + timedelta(minutes=5),
            ),
        ]
    )
    session.commit()


def _seed_cards(session: Session) -> None:
    """准备通知卡牌选择器最小样本。"""
    session.add_all(
        [
            CardSet(code="A1", name="Genetic Apex", label_data='{"zh_CN":"最强的基因"}'),
            Pack(name="Mewtwo", set_code="A1", label_data='{"zh_CN":"超梦"}'),
            Card(
                id=101,
                set_code="A1",
                number=10,
                name="Pikachu",
                rarity="SR",
                image_url="https://example.com/101.png",
                data="{}",
            ),
            Card(
                id=102,
                set_code="A1",
                number=20,
                name="Mewtwo",
                rarity="AR",
                image_url="https://example.com/102.png",
                data="{}",
            ),
            CardPack(card_id=101, pack_name="Mewtwo"),
            CardPack(card_id=102, pack_name="Mewtwo"),
        ]
    )
    session.commit()


def test_build_notifications_context_returns_normalized_query_state(
    session: Session,
) -> None:
    _seed_notifications(session)

    context = build_notifications_context(
        session=session,
        scene="unknown-scene",
        q=" match ",
        sort_by="unknown_field",
        sort_order="sideways",
        page=-3,
        page_size=999,
    )

    assert [row["id"] for row in context["notifications"]] == [2]
    assert context["selected_scene"] == ""
    assert context["sort_by"] == "created_at"
    assert context["sort_order"] == "asc"
    assert context["page"] == 0
    assert context["page_size"] == 100
    assert context["total"] == 1
    assert context["filter_options"]["scene"] == context["scene_options"]
    assert context["filter_options"]["task_type"] == context["task_type_options"]
    assert context["filter_options"]["task_status"] == context["task_status_options"]
    assert context["filter_options"]["rarity_code"] == context["rarity_codes"]


def test_build_notification_card_selector_context_returns_normalized_query_state(
    session: Session,
) -> None:
    _seed_cards(session)

    context = build_notification_card_selector_context(
        session=session,
        scene="rare_card_obtained",
        selected_card_ids=[101],
        q=" pika ",
        sort_by="unknown_field",
        sort_order="sideways",
        page=-2,
        page_size=999,
    )

    assert [row["id"] for row in context["cards"]] == [101]
    assert [row["id"] for row in context["selected_cards"]] == [101]
    assert context["card_selector_sort_by"] == "id"
    assert context["card_selector_sort_order"] == "asc"
    assert context["card_selector_page"] == 0
    assert context["card_selector_page_size"] == 60
    assert context["card_selector_total"] == 1
    assert context["filter_options"]["rarity"] == context["rarity_codes"]
    assert context["filter_options"]["set_code"] == context["set_codes"]
    assert context["filter_options"]["pack_name"] == context["pack_names"]
