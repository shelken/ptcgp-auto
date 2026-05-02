# -*- coding: utf-8 -*-
"""失败任务日志持久化 core E2E 场景。"""

from __future__ import annotations

import json
import logging

from loguru import logger as trace_logger

from ptcgp_auto_v2.config.settings import get_project_root
from ptcgp_auto_v2.core.executor import AccountExecutor
from ptcgp_auto_v2.core.scheduler import SchedulerConfig
from ptcgp_auto_v2.core.task_base import ActionResult, ResetType, Task, TaskRegistry, TaskResult
from ptcgp_auto_v2.core.task_status import TaskStatus
from ptcgp_auto_v2.tests.e2e.harness import create_seed_account_with_task

logger = logging.getLogger(__name__)


class _FakeAdb:
    """E2E core 里避免真实连接设备。"""

    def disconnect(self):
        pass


class _FakePageDetector:
    """E2E core 里只需要支持任务页面加载。"""

    def load_task_pages(self, pages):
        pass


class E2EFailureLogTask(Task):
    """只用于 E2E 的固定失败任务。"""

    task_type = "e2e_failure_log_task"
    reset_type = ResetType.ONCE

    def is_completed(self) -> bool:
        return False

    def handle_page(self, page_name: str, page_info: dict) -> ActionResult:
        return ActionResult.ok(wait=0.0)

    def execute(self, skip_pre_hooks: bool = False) -> TaskResult:
        trace_logger.trace("e2e trace 细节")
        logger.info("e2e failure task running")
        return TaskResult.fail("e2e 故意失败")


def _ensure_task_registered() -> None:
    if TaskRegistry.get_or_none(E2EFailureLogTask.task_type) is not None:
        return
    TaskRegistry.register(E2EFailureLogTask.task_type)(E2EFailureLogTask)


def run(ctx):
    """执行失败任务并检查 JSONL 切片。"""
    ctx.log(ctx.config.description)
    _ensure_task_registered()
    harness = ctx.harness
    account_id, task_id = create_seed_account_with_task(ctx.config.task_type)
    harness.mute_other_accounts(account_id)
    harness.mute_other_tasks_for_account(account_id, ctx.config.task_type)
    harness.ensure_task_pending(account_id, ctx.config.task_type)

    log_dir = get_project_root() / "data" / "logs"
    before = set(log_dir.glob("*task-e2e_failure_log_task*.jsonl")) if log_dir.exists() else set()

    def _fake_prepare_run(executor):
        executor._adb = _FakeAdb()
        executor._recognizer = None
        executor._page_detector = _FakePageDetector()
        return True

    ctx.monkeypatch.setattr(AccountExecutor, "_prepare_run", _fake_prepare_run)

    scheduler = harness.create_scheduler(
        SchedulerConfig(
            poll_interval=0.1,
            max_workers=1,
            task_generation_interval=3600,
            stale_task_check_interval=3600,
        )
    )
    result = scheduler.run_single_task(
        harness.device_addresses[0],
        account_id,
        ctx.config.task_type,
    )
    assert result is False

    snapshot = harness.snapshot_runtime(
        account_id,
        ctx.config.task_type,
        scheduler=scheduler,
    )
    assert snapshot["task_id"] == task_id
    assert snapshot["task_status"] == TaskStatus.FAILED.value

    after = set(log_dir.glob("*task-e2e_failure_log_task*.jsonl"))
    created = sorted(after - before)
    assert len(created) == 1
    log_path = created[0]
    try:
        rows = [json.loads(line) for line in log_path.read_text(encoding="utf-8").splitlines()]
        assert rows[0]["event"] == "task_failure_summary"
        assert rows[0]["account_id"] == account_id
        assert rows[0]["task_type"] == ctx.config.task_type
        assert rows[0]["task_instance_id"] == task_id
        assert rows[0]["failure_reason"] == ctx.config.params["failure_reason"]
        messages = [row.get("message") for row in rows]
        assert "e2e failure task running" in messages
        trace_row = next(row for row in rows if row.get("message") == "e2e trace 细节")
        assert trace_row["level"] == "TRACE"
    finally:
        log_path.unlink(missing_ok=True)

    account_id, task_id = create_seed_account_with_task(ctx.config.task_type)
    harness.mute_other_accounts(account_id)
    harness.mute_other_tasks_for_account(account_id, ctx.config.task_type)
    harness.ensure_task_pending(account_id, ctx.config.task_type)
    before = set(log_dir.glob("*task-e2e_failure_log_task*.jsonl"))

    def _raise_prepare_error(executor):
        raise RuntimeError("device 127.0.0.1:29999 not online")

    ctx.monkeypatch.setattr(AccountExecutor, "_prepare_run", _raise_prepare_error)
    result = scheduler.run_single_task(
        harness.device_addresses[0],
        account_id,
        ctx.config.task_type,
    )
    assert result is False
    snapshot = harness.snapshot_runtime(
        account_id,
        ctx.config.task_type,
        scheduler=scheduler,
    )
    assert snapshot["task_id"] == task_id
    assert snapshot["task_status"] == TaskStatus.FAILED.value

    after = set(log_dir.glob("*task-e2e_failure_log_task*.jsonl"))
    created = sorted(after - before)
    assert len(created) == 1
    log_path = created[0]
    try:
        rows = [json.loads(line) for line in log_path.read_text(encoding="utf-8").splitlines()]
        assert rows[0]["event"] == "task_failure_summary"
        assert rows[0]["account_id"] == account_id
        assert rows[0]["task_instance_id"] == task_id
        assert rows[0]["failure_reason"] == "device 127.0.0.1:29999 not online"
        messages = [row.get("message") for row in rows]
        assert any("账号执行器异常" in str(message) for message in messages)
    finally:
        log_path.unlink(missing_ok=True)
