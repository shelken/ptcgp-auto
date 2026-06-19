# -*- coding: utf-8 -*-
"""调度器退出时自动清理 auto- 实例测试。

覆盖 `Scheduler._cleanup_auto_instances` 行为：
- 退出时关闭所有 auto- 前缀实例
- 跳过非 auto- 实例
"""

from __future__ import annotations

from types import SimpleNamespace

from ptcgp_auto_v2.core.scheduler import Scheduler, SchedulerConfig


def _build_scheduler() -> Scheduler:
    scheduler = Scheduler(
        device_addresses=["127.0.0.1:29999"],
        config=SchedulerConfig(
            poll_interval=0.25,
            task_generation_interval=3600,
            stale_task_check_interval=3600,
        ),
    )
    scheduler._settings = SimpleNamespace(
        auto_create_accounts=False,
        max_accounts=0,
        auto_scale_instance_prefix="auto-",
    )
    scheduler.device_pool = SimpleNamespace(available_count=1, total_count=2)
    scheduler._generate_pending_tasks = lambda: None
    scheduler._check_and_reset_stale_tasks = lambda: None
    scheduler._auto_scale_evaluate = lambda: None
    return scheduler


def test_cleanup_stops_auto_instances_on_exit(monkeypatch):
    """退出调度器时关闭所有 auto- 前缀的 BlueStacks 实例。"""
    scheduler = _build_scheduler()
    scheduler._running = True

    stopped: list[str] = []
    list_args: list[dict] = []

    def _fake_list_manageable(**kw):
        list_args.append(kw)
        return {
            5555: ("Tiramisu64_auto_1", "auto-账号1"),
            5556: ("Tiramisu64_auto_2", "auto-账号2"),
        }

    monkeypatch.setattr(
        "ptcgp_auto_v2.core.scheduler.list_manageable_instances",
        _fake_list_manageable,
    )
    monkeypatch.setattr(
        "ptcgp_auto_v2.core.scheduler.stop_bluestacks_instance",
        lambda name: stopped.append(name),
    )
    monkeypatch.setattr(scheduler, "_main_loop", lambda: None)

    scheduler.run()

    assert list_args == [{"prefix": "auto-"}], "必须传 prefix=auto- 过滤"
    assert "Tiramisu64_auto_1" in stopped
    assert "Tiramisu64_auto_2" in stopped


def test_run_cleanup_skips_non_auto_instances(monkeypatch):
    """退出调度器时通过 prefix=auto- 过滤，跳过非 auto- 实例。"""
    scheduler = _build_scheduler()
    scheduler._running = True

    called_prefix: list[str] = []
    stopped: list[str] = []

    def _fake_list_manageable(*, prefix: str = "auto-"):
        called_prefix.append(prefix)
        # 模拟 list_manageable_instances 的 prefix 过滤行为：只返回 auto- 实例
        return {
            5555: ("Tiramisu64_auto_1", "auto-账号1"),
        }

    monkeypatch.setattr(
        "ptcgp_auto_v2.core.scheduler.list_manageable_instances",
        _fake_list_manageable,
    )
    monkeypatch.setattr(
        "ptcgp_auto_v2.core.scheduler.stop_bluestacks_instance",
        lambda name: stopped.append(name),
    )
    monkeypatch.setattr(scheduler, "_main_loop", lambda: None)

    scheduler.run()

    assert called_prefix == ["auto-"], "必须用 prefix=auto- 过滤"
    assert stopped == ["Tiramisu64_auto_1"], "只停止符合条件的实例"
