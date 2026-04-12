# -*- coding: utf-8 -*-
"""scheduler_idle_backoff core 场景。

这个文件负责验证 deterministic harness 下的空转退避修复。
覆盖待执行任务保持 pending、调度器不误占活跃状态和设备资源释放。
关键依赖是 SchedulerHarness、SchedulerConfig 和 create_seed_account_with_task。
"""

from __future__ import annotations

import time

from ptcgp_auto_v2.core.scheduler import SchedulerConfig
from ptcgp_auto_v2.core.task_status import TaskStatus
from ptcgp_auto_v2.tests.e2e.harness import create_seed_account_with_task


def run(ctx):
    """变更前没有覆盖“有任务但暂时派不出去”的 core 场景。变更后这里固定让派发路径返回 False，并观察调用间隔。变更原因是直接验证主循环是否真的退避到 poll_interval。"""
    ctx.log(ctx.config.description)
    poll_interval = float(ctx.config.params["poll_interval_seconds"])
    observe_cycles = int(ctx.config.params["observe_cycles"])
    harness = ctx.harness
    account_id, task_id = create_seed_account_with_task(ctx.config.task_type)
    harness.mute_other_accounts(account_id)
    harness.mute_other_tasks_for_account(account_id, ctx.config.task_type)
    harness.ensure_task_pending(account_id, ctx.config.task_type)

    scheduler = harness.create_scheduler(
        SchedulerConfig(
            poll_interval=poll_interval,
            max_workers=1,
            task_generation_interval=3600,
            stale_task_check_interval=3600,
        )
    )
    dispatch_call_times: list[float] = []

    def _fake_dispatch(account, task_instances):
        dispatch_call_times.append(time.monotonic())
        assert account.id == account_id
        assert [task.task_type for task in task_instances] == [ctx.config.task_type]
        return False

    ctx.monkeypatch.setattr(scheduler, "_generate_pending_tasks", lambda: None)
    ctx.monkeypatch.setattr(scheduler, "_check_and_reset_stale_tasks", lambda: None)
    ctx.monkeypatch.setattr(scheduler, "_auto_scale_evaluate", lambda: None)
    ctx.monkeypatch.setattr(scheduler, "_dispatch_account_tasks", _fake_dispatch)
    scheduler.start()
    harness._scheduler = scheduler

    harness.wait_until(
        lambda: len(dispatch_call_times) >= observe_cycles,
        timeout_s=poll_interval * (observe_cycles + 6),
        interval_s=max(0.05, poll_interval / 4),
        failure_message="scheduler idle backoff observation timeout",
    )
    harness.stop_scheduler()

    intervals = [
        current - previous
        for previous, current in zip(dispatch_call_times, dispatch_call_times[1:])
    ]
    assert intervals
    assert min(intervals) >= poll_interval * 0.8

    snapshot = harness.snapshot_runtime(
        account_id,
        ctx.config.task_type,
        scheduler=scheduler,
    )
    assert snapshot["task_id"] == task_id
    assert snapshot["task_status"] == TaskStatus.PENDING.value
    assert snapshot["active_in_scheduler"] is False
    assert snapshot["device_summary"]["available"] == 1
    assert snapshot["device_summary"]["busy"] == 0
