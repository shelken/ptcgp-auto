# -*- coding: utf-8 -*-
"""
调度器自动扩缩容单元测试
"""

from datetime import datetime, timedelta

import ptcgp_auto_v2.core.scheduler as scheduler_module
from ptcgp_auto_v2.core.scheduler import Scheduler, SchedulerConfig


def test_auto_scale_evaluate_expansion(monkeypatch):
    """pending 达到阶梯时按 step 触发扩容"""
    config = SchedulerConfig(
        auto_scale_emulators=True,
        auto_scale_eval_interval_seconds=0,
        auto_scale_pending_step=10,
        auto_scale_max_devices=2,
        auto_scale_min_idle_devices=1,
    )
    scheduler = Scheduler(["127.0.0.1:5555"], config=config)
    device = scheduler.device_pool.get_device("127.0.0.1:5555")
    assert device is not None
    device.mark_busy()

    calls: list[str] = []

    monkeypatch.setattr(scheduler, "_count_pending_tasks", lambda: 10)
    monkeypatch.setattr(scheduler, "_refresh_device_pool", lambda *args, **kwargs: None)
    monkeypatch.setattr(scheduler_module, "discover_devices", lambda: [])
    monkeypatch.setattr(
        scheduler_module,
        "list_manageable_instances",
        lambda prefix="auto-": {
            5755: ("Tiramisu64_20", "auto-1"),
            5775: ("Tiramisu64_22", "auto-2"),
        },
    )
    monkeypatch.setattr(
        scheduler_module,
        "start_bluestacks_instance",
        lambda name: calls.append(name) or True,
    )

    scheduler._auto_scale_evaluate()
    assert calls == ["Tiramisu64_20"]


def test_auto_scale_evaluate_scale_down(monkeypatch):
    """空闲时间达到阈值触发缩容"""
    config = SchedulerConfig(
        auto_scale_emulators=True,
        auto_scale_eval_interval_seconds=0,
        auto_scale_pending_step=10,
        auto_scale_max_devices=2,
        auto_scale_min_idle_devices=1,
        auto_scale_idle_seconds=0,
    )
    scheduler = Scheduler(["127.0.0.1:5555", "127.0.0.1:5556"], config=config)
    now = datetime.now()
    for device in scheduler.device_pool.get_all_devices():
        device.mark_available()
        device.became_idle_at = now - timedelta(seconds=200)

    removed: list[str] = []
    stop_calls: list[str] = []

    monkeypatch.setattr(scheduler, "_count_pending_tasks", lambda: 0)
    monkeypatch.setattr(scheduler, "_refresh_device_pool", lambda *args, **kwargs: None)
    monkeypatch.setattr(
        scheduler_module,
        "discover_devices",
        lambda: ["127.0.0.1:5555", "127.0.0.1:5556"],
    )
    monkeypatch.setattr(
        scheduler_module,
        "find_bluestacks_instance_by_port",
        lambda port: (1234, "auto-1"),
    )
    monkeypatch.setattr(
        scheduler_module,
        "stop_bluestacks_instance",
        lambda name: stop_calls.append(name) or True,
    )
    monkeypatch.setattr(
        scheduler.device_pool,
        "remove_device",
        lambda address: removed.append(address) or True,
    )

    scheduler._auto_scale_evaluate()
    assert stop_calls
    assert removed


def test_auto_scale_evaluate_should_not_stop_last_running_device_when_pool_stale(
    monkeypatch,
):
    """设备池存在陈旧设备时，也不能因为虚高 idle 关闭最后一台运行实例"""
    config = SchedulerConfig(
        auto_scale_emulators=True,
        auto_scale_eval_interval_seconds=0,
        auto_scale_pending_step=10,
        auto_scale_max_devices=3,
        auto_scale_min_idle_devices=1,
        auto_scale_idle_seconds=0,
    )
    scheduler = Scheduler(["127.0.0.1:5555", "127.0.0.1:5775"], config=config)

    # 5775 视为陈旧设备（实际已不在 discover 列表）
    running_device = scheduler.device_pool.get_device("127.0.0.1:5555")
    assert running_device is not None
    running_device.mark_available()

    stale_device = scheduler.device_pool.get_device("127.0.0.1:5775")
    assert stale_device is not None
    stale_device.mark_available()

    stop_calls: list[str] = []

    monkeypatch.setattr(scheduler, "_count_pending_tasks", lambda: 0)
    monkeypatch.setattr(
        scheduler_module, "discover_devices", lambda: ["127.0.0.1:5555"]
    )
    monkeypatch.setattr(
        scheduler.device_pool,
        "pick_idle_devices_for_shutdown",
        lambda count, idle_seconds: [running_device],
    )
    monkeypatch.setattr(
        scheduler_module,
        "find_bluestacks_instance_by_port",
        lambda port: (1234, "Tiramisu64_20") if port == 5555 else None,
    )
    monkeypatch.setattr(
        scheduler_module,
        "list_manageable_instances",
        lambda prefix="auto-": {5555: ("Tiramisu64_20", "auto-5555")},
    )
    monkeypatch.setattr(
        scheduler_module,
        "stop_bluestacks_instance",
        lambda name: stop_calls.append(name) or True,
    )

    scheduler._auto_scale_evaluate()
    assert stop_calls == []


def test_auto_scale_evaluate_should_not_add_extra_capacity_when_pending_below_step(
    monkeypatch,
):
    """pending 小于 step 时，不应因 min_idle 额外扩容"""
    config = SchedulerConfig(
        auto_scale_emulators=True,
        auto_scale_eval_interval_seconds=0,
        auto_scale_pending_step=10,
        auto_scale_max_devices=3,
        auto_scale_min_idle_devices=1,
    )
    scheduler = Scheduler(["127.0.0.1:5555"], config=config)
    device = scheduler.device_pool.get_device("127.0.0.1:5555")
    assert device is not None
    device.mark_busy()

    calls: list[str] = []

    monkeypatch.setattr(scheduler, "_count_pending_tasks", lambda: 1)
    monkeypatch.setattr(
        scheduler_module, "discover_devices", lambda: ["127.0.0.1:5555"]
    )
    monkeypatch.setattr(
        scheduler_module,
        "list_manageable_instances",
        lambda prefix="auto-": {
            5755: ("Tiramisu64_20", "auto-1"),
            5775: ("Tiramisu64_22", "auto-2"),
        },
    )
    monkeypatch.setattr(
        scheduler_module,
        "find_bluestacks_instance_by_port",
        lambda port: (1234, "Tiramisu64_20") if port == 5555 else None,
    )
    monkeypatch.setattr(
        scheduler_module,
        "start_bluestacks_instance",
        lambda name: calls.append(name) or True,
    )

    scheduler._auto_scale_evaluate()
    assert calls == []
