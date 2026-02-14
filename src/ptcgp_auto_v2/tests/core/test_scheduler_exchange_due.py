# -*- coding: utf-8 -*-
from datetime import datetime, timedelta
from unittest.mock import patch

import pytest
from sqlmodel import SQLModel, create_engine

from ptcgp_auto_v2.db.models import TaskInstance
from ptcgp_auto_v2.db.repositories.task_instance_repository import (
    TaskInstanceRepository,
)


@pytest.fixture(name="engine")
def engine_fixture():
    """创建内存数据库引擎。"""
    engine = create_engine("sqlite:///:memory:")
    SQLModel.metadata.create_all(engine)
    return engine


@pytest.fixture(name="mock_get_engine")
def mock_get_engine_fixture(engine):
    """将任务仓储引擎替换为测试内存引擎。"""
    with patch(
        "ptcgp_auto_v2.db.repositories.task_instance_repository.get_engine",
        return_value=engine,
    ):
        yield


def test_pending_queries_should_only_return_due_instances(engine, mock_get_engine):
    """pending 查询仅返回 next_run_at 到期的任务。"""
    now = datetime.now()
    repo = TaskInstanceRepository()

    due = TaskInstance(
        account_id=1,
        task_type="exchange_cards",
        status="pending",
        reset_type="once",
        next_run_at=now - timedelta(minutes=1),
    )
    future = TaskInstance(
        account_id=2,
        task_type="exchange_cards",
        status="pending",
        reset_type="once",
        next_run_at=now + timedelta(minutes=5),
    )
    immediate = TaskInstance(
        account_id=3,
        task_type="exchange_cards",
        status="pending",
        reset_type="once",
        next_run_at=None,
    )
    repo.create(due)
    repo.create(future)
    repo.create(immediate)

    account_ids = repo.get_accounts_with_pending_tasks()
    assert 1 in account_ids
    assert 3 in account_ids
    assert 2 not in account_ids

    pending_of_1 = repo.get_pending_by_account(1)
    assert len(pending_of_1) == 1
    assert pending_of_1[0].account_id == 1


def test_ensure_pending_should_clear_next_run_at(engine, mock_get_engine):
    """ensure_pending 应清空 next_run_at 以立即可调度。"""
    now = datetime.now()
    repo = TaskInstanceRepository()

    instance = TaskInstance(
        account_id=10,
        task_type="exchange_cards",
        status="pending",
        reset_type="once",
        next_run_at=now + timedelta(minutes=10),
    )
    repo.create(instance)

    pending = repo.ensure_pending(10, "exchange_cards", "once")
    assert pending.next_run_at is None
