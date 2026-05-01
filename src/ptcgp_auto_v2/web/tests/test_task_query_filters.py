# -*- coding: utf-8 -*-
"""任务页筛选查询回归测试。"""

from __future__ import annotations

from datetime import datetime, timedelta

import pytest
from sqlalchemy.pool import StaticPool
from sqlmodel import SQLModel, Session, create_engine, select

import ptcgp_auto_v2.db.models  # noqa: F401
from ptcgp_auto_v2.db.models.account import Account
from ptcgp_auto_v2.db.models.task_instance import TaskInstance
from ptcgp_auto_v2.web.queries.task_queries import (
    fetch_task_instances,
    reset_completed_task_instances,
)
from ptcgp_auto_v2.web.services.task_service import build_tasks_list_context


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


def _seed_accounts_and_tasks(session: Session) -> None:
    """准备最小账号与任务样本。"""
    now = datetime.now()
    accounts = [
        Account(id=1, game_id="game-ash", nickname="Ash", friend_id="1111000011110000"),
        Account(id=2, game_id="game-misty", nickname="Misty", friend_id="2222000022220000"),
    ]
    tasks = [
        TaskInstance(
            id=1,
            account_id=1,
            task_type="open_pack",
            status="completed",
            next_run_at=now,
        ),
        TaskInstance(
            id=2,
            account_id=1,
            task_type="init_account",
            status="completed",
            next_run_at=now,
        ),
        TaskInstance(
            id=3,
            account_id=2,
            task_type="open_pack",
            status="completed",
            next_run_at=now,
        ),
    ]
    session.add_all(accounts)
    session.add_all(tasks)
    session.commit()


def test_fetch_task_instances_applies_account_query(session: Session) -> None:
    _seed_accounts_and_tasks(session)

    rows, has_next, total = fetch_task_instances(
        session=session,
        page=0,
        page_size=10,
        status=["completed"],
        task_type=[],
        account_id=None,
        account_q="ash",
        sort_by="dispatch_priority",
        sort_order="asc",
    )

    assert [item.id for item in rows] == [1, 2]
    assert has_next is False
    assert total == 2


def test_fetch_task_instances_sorts_next_run_with_empty_values_last(session: Session) -> None:
    _seed_accounts_and_tasks(session)
    base_time = datetime(2026, 4, 30, 8, 0, 0)
    tasks = list(session.exec(select(TaskInstance).order_by(TaskInstance.id)))
    tasks[0].next_run_at = None
    tasks[1].next_run_at = base_time + timedelta(hours=2)
    tasks[2].next_run_at = base_time + timedelta(hours=1)
    session.add_all(tasks)
    session.commit()

    rows, _, _ = fetch_task_instances(
        session=session,
        page=0,
        page_size=10,
        status=["completed"],
        task_type=[],
        account_id=None,
        account_q="",
        sort_by="next_run_at",
        sort_order="asc",
    )

    assert [item.id for item in rows] == [3, 2, 1]


def test_fetch_task_instances_sorts_next_run_empty_values_by_direction(session: Session) -> None:
    _seed_accounts_and_tasks(session)
    tasks = list(session.exec(select(TaskInstance).order_by(TaskInstance.id)))
    for task in tasks:
        task.next_run_at = None
    session.add_all(tasks)
    session.commit()

    asc_rows, _, _ = fetch_task_instances(
        session=session,
        page=0,
        page_size=10,
        status=["completed"],
        task_type=[],
        account_id=None,
        account_q="",
        sort_by="next_run_at",
        sort_order="asc",
    )
    desc_rows, _, _ = fetch_task_instances(
        session=session,
        page=0,
        page_size=10,
        status=["completed"],
        task_type=[],
        account_id=None,
        account_q="",
        sort_by="next_run_at",
        sort_order="desc",
    )

    assert [item.id for item in asc_rows] == [1, 2, 3]
    assert [item.id for item in desc_rows] == [3, 2, 1]


def test_tasks_context_sorts_by_displayed_next_run_at(session: Session) -> None:
    _seed_accounts_and_tasks(session)
    base_time = datetime(2026, 4, 30, 8, 0, 0)
    tasks = list(session.exec(select(TaskInstance).order_by(TaskInstance.id)))
    tasks[0].status = "failed"
    tasks[0].next_run_at = None
    tasks[0].last_completed_at = base_time + timedelta(days=2)
    tasks[1].status = "failed"
    tasks[1].next_run_at = None
    tasks[1].last_completed_at = base_time
    tasks[2].status = "failed"
    tasks[2].next_run_at = None
    tasks[2].last_completed_at = base_time + timedelta(days=1)
    session.add_all(tasks)
    session.commit()

    asc_context = build_tasks_list_context(
        session=session,
        page=0,
        page_size=10,
        status=["failed"],
        sort_by="next_run_at",
        sort_order="asc",
    )
    desc_context = build_tasks_list_context(
        session=session,
        page=0,
        page_size=10,
        status=["failed"],
        sort_by="next_run_at",
        sort_order="desc",
    )

    assert [item["id"] for item in asc_context["items"]] == [2, 3, 1]
    assert [item["id"] for item in desc_context["items"]] == [1, 3, 2]


def test_reset_completed_task_instances_applies_account_query(session: Session) -> None:
    _seed_accounts_and_tasks(session)

    reset_count = reset_completed_task_instances(
        session=session,
        status=["completed"],
        task_type=[],
        account_id=None,
        account_q="ash",
    )

    tasks = list(session.exec(select(TaskInstance).order_by(TaskInstance.id)))

    assert reset_count == 1
    assert tasks[0].status == "pending"
    assert tasks[0].next_run_at is None
    assert tasks[1].status == "completed"
    assert tasks[2].status == "completed"
