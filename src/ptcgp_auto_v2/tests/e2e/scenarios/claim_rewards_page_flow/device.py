# -*- coding: utf-8 -*-
"""claim_rewards 实机 E2E 场景。

这个文件负责验证真实设备执行 claim_rewards 的完成闭环。
覆盖任务结束状态、调度器活跃状态释放和设备资源释放。
"""

from __future__ import annotations

import threading

from ptcgp_auto_v2.config.settings import get_settings
from ptcgp_auto_v2.core.scheduler import SchedulerConfig
from ptcgp_auto_v2.core.task_status import TaskStatus
from ptcgp_auto_v2.infra.adb import AdbController


def _restart_app_for_scenario(device_address: str) -> None:
    """让场景从游戏内开始，而不是继承模拟器桌面/广告页状态。"""
    controller = AdbController(device_address)
    if not controller.connect():
        raise RuntimeError(f"无法连接设备: {device_address}")
    try:
        # 变更原因：实机 E2E 要验证 claim_rewards 流程，不应被 BlueStacks 桌面/广告页初始状态污染。
        controller.restart_app(get_settings().app_package)
    finally:
        controller.disconnect()


def run(ctx):
    """在真实设备上执行 claim_rewards 单任务并验证资源收敛。"""
    ctx.log(ctx.config.description)
    device_config = ctx.require_device_config()
    join_timeout = int(ctx.config.params["join_timeout_seconds"])
    lease_timeout = int(ctx.config.params["lease_timeout_seconds"])
    _restart_app_for_scenario(device_config.device_address)
    harness = ctx.harness
    harness.mute_other_accounts(device_config.account_id)
    harness.mute_other_tasks_for_account(device_config.account_id, ctx.config.task_type)
    harness.ensure_task_pending(device_config.account_id, ctx.config.task_type)

    scheduler = harness.create_scheduler(
        SchedulerConfig(
            poll_interval=0.5,
            max_workers=1,
            task_generation_interval=3600,
            stale_task_check_interval=1,
            stale_task_timeout=lease_timeout,
        )
    )

    result: dict[str, bool] = {}

    def _run_single():
        result["success"] = scheduler.run_single_task(
            device_config.device_address,
            device_config.account_id,
            ctx.config.task_type,
        )

    runner = threading.Thread(target=_run_single, daemon=True)
    runner.start()
    runner.join(timeout=join_timeout)
    if runner.is_alive():
        runner.join(timeout=15)
        raise AssertionError("device claim_rewards completion timeout")

    assert result.get("success") is True
    snapshot = harness.snapshot_runtime(
        device_config.account_id,
        ctx.config.task_type,
        scheduler=scheduler,
    )
    assert snapshot["task_status"] == TaskStatus.COMPLETED.value
    assert snapshot["active_in_scheduler"] is False
    assert snapshot["device_summary"]["available"] == 1
    assert snapshot["device_summary"]["busy"] == 0
