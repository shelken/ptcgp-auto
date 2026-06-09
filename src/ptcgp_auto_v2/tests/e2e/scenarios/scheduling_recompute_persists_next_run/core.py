# -*- coding: utf-8 -*-
"""调度重算落库 core E2E 场景。"""

from __future__ import annotations

import json
from datetime import datetime, timedelta

from ptcgp_auto_v2.core.scheduler import SchedulerConfig
from ptcgp_auto_v2.core.scheduling_service import recompute_and_sync_account_scheduling
from ptcgp_auto_v2.core.task_base import ResetType
from ptcgp_auto_v2.core.task_status import TaskStatus
from ptcgp_auto_v2.db.engine import session_scope
from ptcgp_auto_v2.db.models import AccountTaskPlan, TaskPlan
from ptcgp_auto_v2.db.repositories.factory import RepositoryFactory
from ptcgp_auto_v2.tests.e2e.harness import create_seed_account_with_task


def _attach_interval_plan(account_id: int, task_type: str, interval_seconds: int):
    with session_scope() as session:
        repos = RepositoryFactory(session)
        plan = repos.task_plans().create(
            TaskPlan(
                name=f"e2e_interval_{account_id}",
                description="E2E 调度重算 interval 计划",
                task_types=json.dumps([task_type], ensure_ascii=False),
                configuration=json.dumps(
                    {
                        task_type: {
                            "reset_type": ResetType.INTERVAL.value,
                            "interval_seconds": interval_seconds,
                        }
                    },
                    ensure_ascii=False,
                ),
            )
        )
        if plan.id is None:
            raise RuntimeError("E2E 任务计划 ID 为空")
        session.add(
            AccountTaskPlan(
                account_id=account_id,
                task_plan_id=plan.id,
                priority=10,
                is_active=True,
            )
        )


def _prime_completed_daily_task(task_id: int) -> tuple[datetime, datetime]:
    completed_at = datetime.now() - timedelta(minutes=5)
    original_updated_at = datetime.now() - timedelta(days=1)
    with session_scope() as session:
        repos = RepositoryFactory(session)
        task = repos.task_instances().get_by_id(task_id)
        if task is None:
            raise RuntimeError(f"E2E 任务实例不存在: {task_id}")
        task.status = TaskStatus.COMPLETED.value
        task.reset_type = ResetType.DAILY.value
        task.last_completed_at = completed_at
        task.schedule_anchor_at = completed_at
        task.next_run_at = None
        task.updated_at = original_updated_at
        session.add(task)
    return completed_at, original_updated_at


def _read_task(task_id: int):
    with session_scope() as session:
        repos = RepositoryFactory(session)
        task = repos.task_instances().get_by_id(task_id)
        if task is None:
            raise RuntimeError(f"E2E 任务实例不存在: {task_id}")
        return {
            "status": task.status,
            "reset_type": task.reset_type,
            "next_run_at": task.next_run_at,
            "updated_at": task.updated_at,
        }


def run(ctx):
    """通过真实 recompute 入口验证 same-session 托管任务的调度字段会落库。"""
    ctx.log(ctx.config.description)
    interval_seconds = int(ctx.config.params["interval_seconds"])
    harness = ctx.harness
    account_id, task_id = create_seed_account_with_task(ctx.config.task_type)
    harness.mute_other_accounts(account_id)
    harness.mute_other_tasks_for_account(account_id, ctx.config.task_type)
    _attach_interval_plan(account_id, ctx.config.task_type, interval_seconds)
    completed_at, original_updated_at = _prime_completed_daily_task(task_id)

    with session_scope() as session:
        changed_count = recompute_and_sync_account_scheduling(
            session=session,
            account_id=account_id,
            task_types=[ctx.config.task_type],
        )
    assert changed_count == 1

    persisted = _read_task(task_id)
    expected_next_run_at = completed_at + timedelta(seconds=interval_seconds)
    assert persisted["status"] == TaskStatus.COMPLETED.value
    assert persisted["reset_type"] == ResetType.INTERVAL.value
    assert persisted["next_run_at"] == expected_next_run_at
    assert persisted["updated_at"] > original_updated_at

    scheduler = harness.create_scheduler(
        SchedulerConfig(
            poll_interval=0.1,
            max_workers=1,
            task_generation_interval=3600,
            stale_task_check_interval=3600,
        )
    )
    snapshot = harness.snapshot_runtime(
        account_id,
        ctx.config.task_type,
        scheduler=scheduler,
    )
    assert snapshot["task_id"] == task_id
    assert snapshot["task_status"] == TaskStatus.COMPLETED.value
    assert snapshot["active_in_scheduler"] is False
    assert snapshot["device_summary"]["available"] == 1
    assert snapshot["device_summary"]["busy"] == 0
