# -*- coding: utf-8 -*-
"""调度器空转退避测试。

这个文件负责验证调度器空转退避修复。
覆盖无任务、无法派发和成功派发三条主循环路径。
关键依赖是 Scheduler、AccountSnapshot 和 TaskInstanceSnapshot。
"""

from __future__ import annotations

from datetime import datetime
from types import SimpleNamespace

from ptcgp_auto_v2.core.device_pool import Device
from ptcgp_auto_v2.core.executor import TaskInstanceSnapshot
from ptcgp_auto_v2.core.scheduler import Scheduler, SchedulerConfig
from ptcgp_auto_v2.core.task_status import TaskStatus
from ptcgp_auto_v2.infra.account_syncer import AccountSnapshot


def _build_account_snapshot(account_id: int = 1) -> AccountSnapshot:
    """变更前各用例各自拼账号数据，调度断言容易掺杂无关差异。变更后这里统一生成最小账号快照，让测试只关注派发分支。变更原因是收敛样板数据，减少断言噪音。"""
    now = datetime.now()
    return AccountSnapshot(
        id=account_id,
        game_id=f"game_{account_id}",
        friend_id=None,
        nintendo_id=None,
        nickname=f"account_{account_id}",
        level=None,
        country="SG",
        xml_content=None,
        session_token_iat=None,
        remark="",
        created_at=now,
        updated_at=now,
    )


def _build_task_snapshot(task_type: str) -> TaskInstanceSnapshot:
    """变更前任务样本没有统一入口，状态与顺序断言容易分散。变更后这里统一生成 pending 快照，让断言直指主循环行为。变更原因是固定测试前提，避免样本差异掩盖回归。"""
    now = datetime.now()
    return TaskInstanceSnapshot(
        id=1,
        account_id=1,
        task_type=task_type,
        status=TaskStatus.PENDING.value,
        reset_type="daily",
        error_message=None,
        status_changed_at=now,
        last_completed_at=None,
        schedule_anchor_at=None,
        last_duration_seconds=None,
        next_run_at=None,
        created_at=now,
        updated_at=now,
    )


def _build_scheduler() -> Scheduler:
    """变更前这些测试会碰到设备池和数据库依赖，退避结果不稳定。变更后这里构造只保留主循环骨架的调度器实例。变更原因是隔离外部副作用，让退避断言稳定复现。"""
    scheduler = Scheduler(
        device_addresses=["127.0.0.1:29999"],
        config=SchedulerConfig(
            poll_interval=0.25,
            task_generation_interval=3600,
            stale_task_check_interval=3600,
        ),
    )
    scheduler._settings = SimpleNamespace(auto_create_accounts=False, max_accounts=0)
    scheduler.device_pool = SimpleNamespace(available_count=1)
    scheduler._generate_pending_tasks = lambda: None
    scheduler._check_and_reset_stale_tasks = lambda: None
    scheduler._auto_scale_evaluate = lambda: None
    return scheduler


def test_main_loop_sleeps_when_no_batch(monkeypatch):
    scheduler = _build_scheduler()
    scheduler._running = True
    sleep_calls: list[float] = []

    def _fake_sleep(seconds: float):
        sleep_calls.append(seconds)
        scheduler._running = False

    monkeypatch.setattr("ptcgp_auto_v2.core.scheduler.time.sleep", _fake_sleep)
    monkeypatch.setattr(scheduler, "_get_next_account_batch", lambda: None)

    scheduler._main_loop()

    assert sleep_calls == [scheduler.config.poll_interval]


def test_main_loop_sleeps_when_batch_cannot_dispatch(monkeypatch):
    scheduler = _build_scheduler()
    scheduler._running = True
    account = _build_account_snapshot()
    tasks = [_build_task_snapshot("task_a")]
    sleep_calls: list[float] = []
    dispatch_calls: list[list[str]] = []

    def _fake_sleep(seconds: float):
        sleep_calls.append(seconds)
        scheduler._running = False

    def _fake_dispatch(batch_account, batch_tasks):
        dispatch_calls.append([task.task_type for task in batch_tasks])
        assert batch_account.id == account.id
        return False

    monkeypatch.setattr("ptcgp_auto_v2.core.scheduler.time.sleep", _fake_sleep)
    monkeypatch.setattr(scheduler, "_get_next_account_batch", lambda: (account, tasks))
    monkeypatch.setattr(scheduler, "_dispatch_account_tasks", _fake_dispatch)

    scheduler._main_loop()

    assert dispatch_calls == [["task_a"]]
    assert sleep_calls == [scheduler.config.poll_interval]
    assert [task.status for task in tasks] == [TaskStatus.PENDING.value]


def test_main_loop_skips_extra_sleep_after_successful_dispatch(monkeypatch):
    scheduler = _build_scheduler()
    scheduler._running = True
    account = _build_account_snapshot()
    tasks = [_build_task_snapshot("task_a"), _build_task_snapshot("task_b")]
    sleep_calls: list[float] = []
    dispatch_calls: list[list[str]] = []

    def _fake_sleep(seconds: float):
        sleep_calls.append(seconds)

    def _fake_dispatch(batch_account, batch_tasks):
        dispatch_calls.append([task.task_type for task in batch_tasks])
        assert batch_account.id == account.id
        scheduler._running = False
        return True

    monkeypatch.setattr("ptcgp_auto_v2.core.scheduler.time.sleep", _fake_sleep)
    monkeypatch.setattr(scheduler, "_get_next_account_batch", lambda: (account, tasks))
    monkeypatch.setattr(scheduler, "_dispatch_account_tasks", _fake_dispatch)

    scheduler._main_loop()

    assert dispatch_calls == [["task_a", "task_b"]]
    assert sleep_calls == []
    assert [task.status for task in tasks] == [
        TaskStatus.PENDING.value,
        TaskStatus.PENDING.value,
    ]


def test_dispatch_account_tasks_returns_true_and_preserves_task_order(monkeypatch):
    scheduler = _build_scheduler()
    account = _build_account_snapshot()
    tasks = [_build_task_snapshot("task_a"), _build_task_snapshot("task_b")]
    acquired_ids: list[int] = []
    submitted_payload: list[tuple[str, list[str]]] = []

    class _StubDevicePool:
        available_count = 1

        def acquire_for_account(self, account_id: int):
            acquired_ids.append(account_id)
            return Device(address="127.0.0.1:29999")

    def _fake_submit(device, submit_account, submit_tasks):
        submitted_payload.append(
            (
                device.address,
                [task.task_type for task in submit_tasks],
            )
        )
        assert submit_account.id == account.id

    scheduler.device_pool = _StubDevicePool()
    monkeypatch.setattr(scheduler, "_submit_account_executor", _fake_submit)

    dispatched = scheduler._dispatch_account_tasks(account, tasks)

    assert dispatched is True
    assert acquired_ids == [account.id]
    assert submitted_payload == [("127.0.0.1:29999", ["task_a", "task_b"])]
    assert [task.status for task in tasks] == [
        TaskStatus.PENDING.value,
        TaskStatus.PENDING.value,
    ]
