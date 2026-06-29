# -*- coding: utf-8 -*-
"""主入口自启动逻辑测试。

只测试自动拉起 BlueStacks 实例的 helper，不调用 main()，避免触发 argparse、scheduler 或真实本机进程。
"""

from __future__ import annotations

from ptcgp_auto_v2 import main as main_module
from ptcgp_auto_v2.main import (
    AUTO_START_PORT_INTERVAL_SECONDS,
    AUTO_START_PORT_TIMEOUT_SECONDS,
    _start_manageable_instances,
)


def test_start_manageable_instances_starts_all_and_returns_ready_addresses(
    monkeypatch,
):
    """无运行中设备时，启动所有 auto 实例，并返回端口已就绪的地址。"""
    auto_instances = {
        5555: ("Tiramisu64_auto_1", "auto-账号1"),
        5556: ("Tiramisu64_auto_2", "auto-账号2"),
    }
    started: list[str] = []
    waited: list[tuple[str, int, int]] = []

    def fake_start(instance_name: str):
        started.append(instance_name)
        return True

    def fake_wait(
        addr: str,
        timeout_seconds: int,
        interval_seconds: int,
    ):
        waited.append((addr, timeout_seconds, interval_seconds))
        return True

    monkeypatch.setattr(main_module, "start_bluestacks_instance", fake_start)
    monkeypatch.setattr(main_module, "wait_for_bluestacks_port", fake_wait)

    addresses = _start_manageable_instances(auto_instances)

    assert started == ["Tiramisu64_auto_1", "Tiramisu64_auto_2"]
    assert addresses == ["127.0.0.1:5555", "127.0.0.1:5556"]
    assert waited == [
        (
            "127.0.0.1:5555",
            AUTO_START_PORT_TIMEOUT_SECONDS,
            AUTO_START_PORT_INTERVAL_SECONDS,
        ),
        (
            "127.0.0.1:5556",
            AUTO_START_PORT_TIMEOUT_SECONDS,
            AUTO_START_PORT_INTERVAL_SECONDS,
        ),
    ]


def test_start_manageable_instances_skips_timeout_ports(monkeypatch):
    """部分实例端口未就绪时，只返回已就绪设备。"""
    auto_instances = {
        5555: ("Tiramisu64_auto_1", "auto-账号1"),
        5556: ("Tiramisu64_auto_2", "auto-账号2"),
    }

    monkeypatch.setattr(
        main_module,
        "start_bluestacks_instance",
        lambda instance_name: True,
    )
    monkeypatch.setattr(
        main_module,
        "wait_for_bluestacks_port",
        lambda addr, **_kw: addr == "127.0.0.1:5555",
    )

    addresses = _start_manageable_instances(auto_instances)

    assert addresses == ["127.0.0.1:5555"]
