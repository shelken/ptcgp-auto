# -*- coding: utf-8 -*-
"""管理页基础列表查询状态回归测试。"""

from __future__ import annotations

from datetime import datetime, timedelta

import pytest
from sqlalchemy.pool import StaticPool
from sqlmodel import SQLModel, Session, create_engine

import ptcgp_auto_v2.db.models  # noqa: F401
from ptcgp_auto_v2.db.models.account import Account
from ptcgp_auto_v2.db.models.account_pack_point import AccountPackPoint
from ptcgp_auto_v2.db.models.account_stat import AccountStat
from ptcgp_auto_v2.db.models.task_plan import TaskPlan
from ptcgp_auto_v2.web.services.account_service import build_accounts_list_context
from ptcgp_auto_v2.web.services.plan_service import build_plans_list_context
from ptcgp_auto_v2.web.services.resource_service import build_resources_context


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


def _seed_accounts_and_resources(session: Session) -> None:
    """准备账号与资源最小样本。"""
    base = datetime(2026, 4, 14, 12, 0, 0)
    session.add_all(
        [
            Account(
                id=1,
                game_id="game-ash",
                nickname="Ash",
                friend_id="1111000011110000",
                updated_at=base,
            ),
            Account(
                id=2,
                game_id="game-misty",
                nickname="Misty",
                friend_id="2222000022220000",
                updated_at=base + timedelta(minutes=5),
            ),
        ]
    )
    session.add_all(
        [
            AccountStat(account_id=1, exchange_points=80, pack_hourglass_count=5),
            AccountStat(account_id=2, exchange_points=120, pack_hourglass_count=8),
            AccountPackPoint(account_id=1, series="A1", points=40),
            AccountPackPoint(account_id=2, series="A1", points=70),
        ]
    )
    session.commit()


def _seed_plans(session: Session) -> None:
    """准备任务计划最小样本。"""
    session.add_all(
        [
            TaskPlan(id=1, name="Alpha Plan", description="first"),
            TaskPlan(id=2, name="Beta Plan", description="second"),
        ]
    )
    session.commit()


def test_build_accounts_list_context_returns_normalized_query_state(
    session: Session,
) -> None:
    _seed_accounts_and_resources(session)

    context = build_accounts_list_context(
        session=session,
        q="  mist  ",
        sort_by="unknown_field",
        sort_order="sideways",
        page=-3,
        page_size=999,
    )

    assert [row["id"] for row in context["items"]] == [2]
    assert context["sort_by"] == "id"
    assert context["sort_order"] == "asc"
    assert context["page"] == 0
    assert context["page_size"] == 100
    assert context["total"] == 1


def test_build_plans_list_context_returns_normalized_query_state(
    session: Session,
) -> None:
    _seed_plans(session)

    context = build_plans_list_context(
        session=session,
        q=" beta ",
        sort_by="unknown_field",
        sort_order="sideways",
        page=-2,
        page_size=999,
    )

    assert [row["id"] for row in context["items"]] == [2]
    assert context["sort_by"] == "id"
    assert context["sort_order"] == "asc"
    assert context["page"] == 0
    assert context["page_size"] == 100
    assert context["total"] == 1


def test_build_resources_context_normalizes_view_specific_query_state(
    session: Session,
) -> None:
    _seed_accounts_and_resources(session)

    context = build_resources_context(
        session=session,
        view="pack-points",
        q=" misty ",
        sort_by="exchange_points",
        sort_order="sideways",
        page=-5,
        page_size=999,
    )

    assert [row["account_id"] for row in context["items"]] == [2]
    assert context["view"] == "pack-points"
    assert context["sort_by"] == "id"
    assert context["sort_order"] == "asc"
    assert context["page"] == 0
    assert context["page_size"] == 100
    assert context["total"] == 1
