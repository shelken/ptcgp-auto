# -*- coding: utf-8 -*-
"""设备池归还与不健康熔断。"""

from __future__ import annotations

from ptcgp_auto_v2.core.device_pool import DevicePool, DeviceStatus


def test_release_as_unhealthy_stops_acquire():
    """归还时标 unhealthy 后，acquire 不得再分发该设备。"""
    pool = DevicePool(["127.0.0.1:5785", "127.0.0.1:5555"])
    dead = pool.acquire()
    assert dead is not None
    assert dead.address == "127.0.0.1:5785"

    pool.release(dead, unhealthy=True)

    summary = pool.get_status_summary()
    assert summary["unhealthy"] == 1
    assert summary["available"] == 1

    next_dev = pool.acquire()
    assert next_dev is not None
    assert next_dev.address == "127.0.0.1:5555"

    assert pool.acquire() is None


def test_release_healthy_returns_to_available():
    pool = DevicePool(["127.0.0.1:5785"])
    device = pool.acquire()
    assert device is not None
    pool.release(device)
    assert device.status == DeviceStatus.AVAILABLE
    assert pool.available_count == 1


def test_adb_unhealthy_flag_drives_release_circuit_break(monkeypatch):
    """重启失败挂起标记 → release(unhealthy=True) → acquire 不再分发。"""
    from ptcgp_auto_v2.infra.adb import AdbController

    address = "127.0.0.1:5785"
    AdbController._offline_failures.clear()
    AdbController._unhealthy_devices.clear()

    pool = DevicePool([address, "127.0.0.1:5555"])
    device = pool.acquire()
    assert device is not None
    assert device.address == address

    controller = AdbController(address)
    monkeypatch.setattr(controller, "_should_restart_emulator", lambda: True)
    monkeypatch.setattr(
        "ptcgp_auto_v2.infra.adb.restart_bluestacks_instance_for_device",
        lambda _addr: False,
    )

    from ptcgp_auto_v2.config.constants import ADB_CONNECT_FAIL_RESTART_THRESHOLD

    for _ in range(ADB_CONNECT_FAIL_RESTART_THRESHOLD):
        controller.register_offline_failure(
            RuntimeError(f"device {address} not online"),
        )

    assert AdbController.is_marked_unhealthy(address)
    pool.release(device, unhealthy=AdbController.is_marked_unhealthy(address))

    next_dev = pool.acquire()
    assert next_dev is not None
    assert next_dev.address == "127.0.0.1:5555"
    assert pool.acquire() is None
