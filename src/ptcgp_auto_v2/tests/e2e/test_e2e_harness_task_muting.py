# -*- coding: utf-8 -*-
"""E2E harness 任务静默写库测试。

这个文件负责验证 harness 的任务静默方法能兼容当前 TaskInstance 模型。之前静默更新仍写入已移除的 owner_run_id，导致实机场景在进入任务前直接失败。现在锁定静默方法只写当前模型存在的字段。
"""

from __future__ import annotations

from datetime import datetime, timedelta

from ptcgp_auto_v2.db.engine import session_scope
from ptcgp_auto_v2.db.repositories.factory import RepositoryFactory
from ptcgp_auto_v2.tests.e2e.harness import create_seed_account_with_task


def test_mute_other_accounts_marks_non_target_tasks_completed(core_harness):
    """静默其他账号时，应只更新当前模型已有字段。"""
    target_account_id, _ = create_seed_account_with_task("fetch_account_info")
    other_account_id, other_task_id = create_seed_account_with_task("claim_gifts")

    del other_account_id
    core_harness.mute_other_accounts(target_account_id)

    with session_scope() as session:
        repos = RepositoryFactory(session)
        task = repos.task_instances().get_by_id(other_task_id)
        assert task is not None
        assert task.status == "completed"
        assert task.error_message is None
        assert task.last_completed_at is not None
        assert task.schedule_anchor_at is not None
        assert task.next_run_at is not None


def test_mute_other_tasks_for_account_keeps_selected_task(core_harness):
    """静默同账号其他任务时，应保留目标任务并完成其余任务。"""
    account_id, fetch_task_id = create_seed_account_with_task("fetch_account_info")
    with session_scope() as session:
        repos = RepositoryFactory(session)
        extra_task = repos.task_instances().get_or_create(
            account_id=account_id,
            task_type="claim_gifts",
            reset_type="daily",
        )
        if extra_task.id is None:
            raise RuntimeError("extra task id is None")
        repos.task_instances().update_runtime_state(
            extra_task.id,
            status="failed",
            error_message="old error",
            next_run_at=datetime.now() + timedelta(hours=1),
        )
        extra_task_id = extra_task.id

    core_harness.mute_other_tasks_for_account(account_id, "fetch_account_info")

    with session_scope() as session:
        repos = RepositoryFactory(session)
        kept_task = repos.task_instances().get_by_id(fetch_task_id)
        muted_task = repos.task_instances().get_by_id(extra_task_id)
        assert kept_task is not None
        assert muted_task is not None
        assert kept_task.status == "pending"
        assert muted_task.status == "completed"
        assert muted_task.error_message is None
        assert muted_task.last_completed_at is not None
