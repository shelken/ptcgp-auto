# -*- coding: utf-8 -*-
"""交换任务 runtime 延时重排 core E2E 场景。"""

from __future__ import annotations

from datetime import datetime, timedelta
from types import SimpleNamespace

from ptcgp_auto_v2.core.executor import AccountExecutor
from ptcgp_auto_v2.core.scheduler import SchedulerConfig
from ptcgp_auto_v2.core.task_base import ActionResult, ResetType, Task, TaskRegistry
from ptcgp_auto_v2.core.task_status import TaskStatus
from ptcgp_auto_v2.db.engine import session_scope
from ptcgp_auto_v2.db.repositories.factory import RepositoryFactory
from ptcgp_auto_v2.hooks import ExchangeDelayPostHook
from ptcgp_auto_v2.tests.e2e.harness import create_seed_account_with_task


class _FakeAdb:
    """E2E core 中避免真实设备连接。"""

    def disconnect(self):
        pass


class _FakePageDetector:
    """E2E core 中只需要满足任务页面加载接口。"""

    def load_task_pages(self, pages):
        pass


class E2EExchangeTask(Task):
    """只用于 E2E 的 exchange_cards 替身，保留真实后置 Hook 链路。"""

    task_type = "exchange_cards"
    reset_type = ResetType.DAILY
    runtime_delay_seconds: float | None = None
    runtime_delay_reason: str | None = None
    use_legacy_delay_fields = False

    def on_start(self):
        if self.use_legacy_delay_fields:
            # 变更原因：负例要模拟旧任务动态字段，同时避免 vulture 把测试专用属性误判为死代码。
            setattr(self, "_delay_seconds", self.runtime_delay_seconds)
            setattr(self, "_delay_reason", self.runtime_delay_reason)
            return
        self._ctx = SimpleNamespace(
            runtime=SimpleNamespace(
                delay_seconds=self.runtime_delay_seconds,
                delay_reason=self.runtime_delay_reason,
            )
        )

    def is_completed(self) -> bool:
        return True

    def handle_page(self, page_name: str, page_info: dict) -> ActionResult:
        return ActionResult.ok(wait=0.0)

    def get_post_hooks(self) -> list:
        return [ExchangeDelayPostHook()]


def _install_fake_exchange_task(monkeypatch):
    monkeypatch.setitem(TaskRegistry._tasks, "exchange_cards", E2EExchangeTask)


def _patch_executor_prepare(monkeypatch):
    def _fake_prepare_run(executor):
        executor._adb = _FakeAdb()
        executor._recognizer = None
        executor._page_detector = _FakePageDetector()
        return True

    monkeypatch.setattr(AccountExecutor, "_prepare_run", _fake_prepare_run)


def _read_task(account_id: int, task_type: str):
    with session_scope() as session:
        repos = RepositoryFactory(session)
        task = repos.task_instances().get_by_account_and_type(account_id, task_type)
        if task is None:
            raise RuntimeError(f"E2E 任务实例不存在: {account_id}/{task_type}")
        return {
            "id": task.id,
            "status": task.status,
            "next_run_at": task.next_run_at,
            "error_message": task.error_message,
        }


def _run_single_exchange(ctx, *, runtime_delay: bool):
    E2EExchangeTask.runtime_delay_seconds = float(
        ctx.config.params["runtime_delay_seconds"]
    )
    E2EExchangeTask.runtime_delay_reason = str(
        ctx.config.params["runtime_delay_reason"]
    )
    E2EExchangeTask.use_legacy_delay_fields = not runtime_delay

    harness = ctx.harness
    account_id, task_id = create_seed_account_with_task(ctx.config.task_type)
    harness.mute_other_accounts(account_id)
    harness.mute_other_tasks_for_account(account_id, ctx.config.task_type)
    harness.ensure_task_pending(account_id, ctx.config.task_type)

    scheduler = harness.create_scheduler(
        SchedulerConfig(
            poll_interval=0.1,
            max_workers=1,
            task_generation_interval=3600,
            stale_task_check_interval=3600,
        )
    )
    started_at = datetime.now()
    result = scheduler.run_single_task(
        harness.device_addresses[0],
        account_id,
        ctx.config.task_type,
    )
    snapshot = harness.snapshot_runtime(
        account_id,
        ctx.config.task_type,
        scheduler=scheduler,
    )
    persisted = _read_task(account_id, ctx.config.task_type)
    assert snapshot["task_id"] == task_id
    assert snapshot["active_in_scheduler"] is False
    assert snapshot["device_summary"]["available"] == 1
    assert snapshot["device_summary"]["busy"] == 0
    return result, persisted, started_at


def run(ctx):
    """通过真实执行器后置 Hook flow 验证 runtime delay 才会触发重排。"""
    ctx.log(ctx.config.description)
    _install_fake_exchange_task(ctx.monkeypatch)
    _patch_executor_prepare(ctx.monkeypatch)

    result, persisted, started_at = _run_single_exchange(ctx, runtime_delay=True)
    assert result is False
    assert persisted["status"] == TaskStatus.PENDING.value
    assert persisted["next_run_at"] is not None
    assert persisted["next_run_at"] >= started_at + timedelta(
        seconds=float(ctx.config.params["runtime_delay_seconds"]) - 1
    )
    assert persisted["error_message"] == (
        f"等待复查: {ctx.config.params['runtime_delay_reason']}"
    )

    result, persisted, _ = _run_single_exchange(ctx, runtime_delay=False)
    assert result is True
    assert persisted["status"] == TaskStatus.COMPLETED.value
    assert persisted["next_run_at"] is not None
    assert persisted["error_message"] is None
