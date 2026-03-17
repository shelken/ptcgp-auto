# -*- coding: utf-8 -*-
"""TaskInstanceRepository 重置逻辑测试。"""

from datetime import datetime, timedelta

from sqlmodel import Session, select

from ptcgp_auto_v2.db.models import TaskInstance
from ptcgp_auto_v2.db.repositories import TaskInstanceRepository


def _seed_task_instance(
    session: Session,
    status: str,
    updated_at: datetime,
    account_id: int = 1,
    task_type: str = "open_pack",
):
    task = TaskInstance(
        account_id=account_id,
        task_type=task_type,
        status=status,
        updated_at=updated_at,
    )
    session.add(task)
    session.commit()
    session.refresh(task)
    return task


def test_reset_stale_tasks_force_all(session: Session):
    """force_all=True 时应直接重置所有异常状态。"""
    now = datetime.now()
    _seed_task_instance(session, "running", now - timedelta(minutes=5))
    _seed_task_instance(session, "blocked", now - timedelta(minutes=5))
    _seed_task_instance(session, "skipped", now)
    _seed_task_instance(session, "failed", now)

    repo = TaskInstanceRepository()
    updated = repo.reset_stale_tasks(force_all=True)

    assert updated == 4
    statuses = [row.status for row in session.exec(select(TaskInstance)).all()]
    assert all(status == "pending" for status in statuses)


def test_reset_stale_tasks_respects_cooldown(session: Session):
    """force_all=False 时应按超时/冷却筛选。"""
    now = datetime.now()
    stale = now - timedelta(seconds=120)
    fresh = now - timedelta(seconds=10)

    running = _seed_task_instance(session, "running", stale, account_id=1)
    blocked = _seed_task_instance(session, "blocked", fresh, account_id=2)
    skipped = _seed_task_instance(session, "skipped", stale, account_id=3)
    failed = _seed_task_instance(session, "failed", fresh, account_id=4)

    repo = TaskInstanceRepository()
    updated = repo.reset_stale_tasks(
        stale_timeout_seconds=60,
        skipped_timeout_seconds=60,
    )

    assert updated == 2

    session.refresh(running)
    session.refresh(blocked)
    session.refresh(skipped)
    session.refresh(failed)

    assert running.status == "pending"
    assert blocked.status == "blocked"
    assert skipped.status == "pending"
    assert failed.status == "failed"
