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


def test_auto_scale_evaluate_scale_down_by_target_device_count(monkeypatch):
    """总运行设备数高于目标值时，按目标设备数缩容 auto 实例"""
    config = SchedulerConfig(
        auto_scale_emulators=True,
        auto_scale_eval_interval_seconds=0,
        auto_scale_pending_step=10,
        auto_scale_max_devices=3,
        auto_scale_min_idle_devices=1,
        auto_scale_idle_seconds=0,
    )
    scheduler = Scheduler(
        ["127.0.0.1:5555", "127.0.0.1:5556", "127.0.0.1:5557"],
        config=config,
    )
    now = datetime.now()
    device_5555 = scheduler.device_pool.get_device("127.0.0.1:5555")
    device_5556 = scheduler.device_pool.get_device("127.0.0.1:5556")
    device_5557 = scheduler.device_pool.get_device("127.0.0.1:5557")
    assert device_5555 is not None
    assert device_5556 is not None
    assert device_5557 is not None
    device_5555.mark_busy()
    device_5556.mark_available()
    device_5556.became_idle_at = now - timedelta(seconds=200)
    device_5557.mark_available()
    device_5557.became_idle_at = now - timedelta(seconds=200)

    removed: list[str] = []
    stop_calls: list[str] = []

    monkeypatch.setattr(scheduler, "_count_pending_tasks", lambda: 9)
    monkeypatch.setattr(scheduler, "_refresh_device_pool", lambda *args, **kwargs: None)
    monkeypatch.setattr(
        scheduler_module,
        "discover_devices",
        lambda: ["127.0.0.1:5555", "127.0.0.1:5556", "127.0.0.1:5557"],
    )
    monkeypatch.setattr(
        scheduler_module,
        "list_manageable_instances",
        lambda prefix="auto-": {
            5556: ("Tiramisu64_21", "auto-2"),
            5557: ("Tiramisu64_22", "auto-3"),
        },
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
    assert stop_calls == ["Tiramisu64_21", "Tiramisu64_22"]
    assert removed == ["127.0.0.1:5556", "127.0.0.1:5557"]


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
        "start_bluestacks_instance",
        lambda name: calls.append(name) or True,
    )

    scheduler._auto_scale_evaluate()
    assert calls == []


def test_auto_scale_evaluate_should_not_stop_non_auto_idle_device(monkeypatch):
    """缩容只能关闭可管理的 auto 实例，不能碰普通运行设备"""
    config = SchedulerConfig(
        auto_scale_emulators=True,
        auto_scale_eval_interval_seconds=0,
        auto_scale_pending_step=10,
        auto_scale_max_devices=3,
        auto_scale_min_idle_devices=1,
        auto_scale_idle_seconds=0,
    )
    scheduler = Scheduler(["127.0.0.1:5555", "127.0.0.1:5556"], config=config)
    now = datetime.now()

    fixed_device = scheduler.device_pool.get_device("127.0.0.1:5555")
    auto_device = scheduler.device_pool.get_device("127.0.0.1:5556")
    assert fixed_device is not None
    assert auto_device is not None
    fixed_device.mark_available()
    fixed_device.became_idle_at = now - timedelta(seconds=200)
    auto_device.mark_available()
    auto_device.became_idle_at = now - timedelta(seconds=200)

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
        "list_manageable_instances",
        lambda prefix="auto-": {5556: ("Tiramisu64_21", "auto-2")},
    )
    monkeypatch.setattr(
        scheduler_module,
        "stop_bluestacks_instance",
        lambda name: stop_calls.append(name) or True,
    )

    scheduler._auto_scale_evaluate()
    assert stop_calls == ["Tiramisu64_21"]
