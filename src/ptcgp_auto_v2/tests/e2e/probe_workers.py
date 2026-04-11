# -*- coding: utf-8 -*-
"""E2E 测试专用执行器探针。"""

from __future__ import annotations

import time
from datetime import datetime, timedelta

import ptcgp_auto_v2.tasks  # noqa: F401
from ptcgp_auto_v2.core.executor import AccountExecutor
from ptcgp_auto_v2.core.task_status import TaskStatus
from ptcgp_auto_v2.db.engine import session_scope
from ptcgp_auto_v2.db.repositories.factory import RepositoryFactory


def _prepare_probe_executor(executor: AccountExecutor, *, claim_first_task: bool = False):
    executor._activate_run_lease()
    executor._heartbeat_runtime()
    if not claim_first_task or not executor.task_instances:
        return None
    task = executor.task_instances[0]
    if not executor._claim_task_for_execution(task, executor.account):
        raise RuntimeError(f"探针认领失败: {task.task_type}")
    return task


def _finish_probe_executor(executor: AccountExecutor):
    executor._mark_run_lease_finishing()
    executor._cleanup()
    executor._finish_run_lease()


def probe_complete_run(executor: AccountExecutor):
    """之前探针写 completed 时仍传入已删除的 owner_run_id。现在只更新当前模型保留的运行态字段。这样完成态探针能继续驱动当前仓库的 E2E 回收场景。"""
    now = datetime.now()
    with executor._bind_log_context(executor.account):
        _prepare_probe_executor(executor)
        for task in executor.task_instances:
            if task.id is None:
                continue
            if not executor._claim_task_for_execution(task, executor.account):
                raise RuntimeError(f"探针认领失败: {task.task_type}")
            task.status = TaskStatus.COMPLETED.value
            task.error_message = None
            task.last_completed_at = now
            task.schedule_anchor_at = now
            task.next_run_at = now + timedelta(days=1)
            with session_scope() as session:
                repos = RepositoryFactory(session)
                repos.task_instances().update_runtime_state(
                    task.id,
                    status=TaskStatus.COMPLETED.value,
                    error_message=None,
                    last_completed_at=now,
                    schedule_anchor_at=now,
                    next_run_at=now + timedelta(days=1),
                )
        _finish_probe_executor(executor)


def probe_hang_run(executor: AccountExecutor):
    """确定性卡死：上报一次心跳后无限阻塞，不执行清理。"""
    with executor._bind_log_context(executor.account):
        _prepare_probe_executor(executor, claim_first_task=True)
        while True:
            time.sleep(60)


def probe_mark_running(executor: AccountExecutor):
    """之前 running 探针会写入已删除的 owner_run_id。现在只保留状态和调度字段写入。这样探针仍能稳定制造当前模型下的 running 卡死现场。"""
    with executor._bind_log_context(executor.account):
        task = _prepare_probe_executor(executor, claim_first_task=True)
        if not executor.task_instances:
            while True:
                time.sleep(60)
        task = task or executor.task_instances[0]
        if task.id is not None:
            now = datetime.now()
            with session_scope() as session:
                repos = RepositoryFactory(session)
                repos.task_instances().update_runtime_state(
                    task.id,
                    status=TaskStatus.RUNNING.value,
                    error_message=None,
                    next_run_at=None,
                )
            task.status = TaskStatus.RUNNING.value
            task.updated_at = now
        while True:
            time.sleep(60)


def probe_complete_after_pending(
    executor: AccountExecutor,
    *,
    task_type: str,
):
    """之前 pending 收口探针仍写入已删除的 owner_run_id。现在只写当前任务实例真实存在的收口字段。这样指定任务完成场景不会再被旧模型参数拦住。"""
    with executor._bind_log_context(executor.account):
        _prepare_probe_executor(executor)
        with session_scope() as session:
            repos = RepositoryFactory(session)
            instance = repos.task_instances().get_by_account_and_type(
                executor.account.id,
                task_type,
            )
            if instance is None or instance.id is None:
                executor._cleanup()
                return
            now = datetime.now()
            repos.task_instances().update_runtime_state(
                instance.id,
                status=TaskStatus.COMPLETED.value,
                error_message=None,
                last_completed_at=now,
                schedule_anchor_at=now,
                next_run_at=now + timedelta(days=1),
            )
        _finish_probe_executor(executor)


def mark_task_completed_by_id(task_id: int):
    """之前辅助方法会携带已删除的 owner_run_id。现在只写当前模型存在的 completed 字段。这样测试准备步骤能兼容迁移后的仓库模型。"""
    with session_scope() as session:
        repos = RepositoryFactory(session)
        instance = repos.task_instances().get_by_id(task_id)
        if instance is None:
            return
        now = datetime.now()
        repos.task_instances().update_runtime_state(
            task_id,
            status=TaskStatus.COMPLETED.value,
            error_message=None,
            last_completed_at=now,
            schedule_anchor_at=now,
            next_run_at=now + timedelta(days=1),
        )
