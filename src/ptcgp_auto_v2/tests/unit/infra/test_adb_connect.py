# -*- coding: utf-8 -*-
"""ADB 连接路径测试。

这个文件负责验证 ADB 控制器的连接阶段不会把 `u2.connect` 放进后台线程。之前连接阶段复用了底层调用超时包装，导致 `u2.connect` 在后台线程里超时卡死。现在锁定连接动作必须在调用线程执行，其他设备调用仍保持原来的 failfast 包装。
"""

from __future__ import annotations

from http.client import RemoteDisconnected
import threading

from PIL import Image
import uiautomator2 as u2

from ptcgp_auto_v2.config.constants import ADB_CONNECT_FAIL_RESTART_THRESHOLD
from ptcgp_auto_v2.infra.adb import AdbController


def test_connect_device_calls_u2_connect_on_current_thread(monkeypatch):
    """连接阶段必须在当前线程执行 u2.connect。"""
    controller = AdbController("127.0.0.1:5555")
    current_thread = threading.current_thread()
    captured: dict[str, object] = {}

    def fake_connect(address: str):
        captured["address"] = address
        captured["thread"] = threading.current_thread()
        return object()

    monkeypatch.setattr("ptcgp_auto_v2.infra.adb.u2.connect", fake_connect)

    device = controller._connect_device("u2.connect")

    assert device is not None
    assert captured["address"] == "127.0.0.1:5555"
    assert captured["thread"] is current_thread


def test_call_device_runs_callback_on_current_thread():
    """设备调用阶段也必须在当前线程执行。"""
    controller = AdbController("127.0.0.1:5555")
    current_thread = threading.current_thread()
    captured: dict[str, object] = {}

    def fake_call():
        captured["thread"] = threading.current_thread()
        return "ok"

    result = controller._call_device("screenshot", fake_call)

    assert result == "ok"
    assert captured["thread"] is current_thread


class _FlakyScreenshotDevice:
    def __init__(self):
        self.calls = 0

    def screenshot(self, **_kwargs):
        self.calls += 1
        if self.calls == 1:
            raise RemoteDisconnected("Remote end closed connection without response")
        return Image.new("RGB", (10, 20), "black")


def test_screenshot_reconnects_once_after_remote_disconnect(monkeypatch):
    """截图 HTTP 连接瞬断时应重连并重试一次，不把可恢复的 uiautomator2 抖动误判为任务失败。"""
    controller = AdbController("127.0.0.1:5555")
    device = _FlakyScreenshotDevice()
    reconnects: list[str] = []
    controller.device = device

    def fake_connect(operation: str):
        reconnects.append(operation)
        return device

    monkeypatch.setattr(controller, "_connect_device", fake_connect)

    image = controller.screenshot()

    assert image is not None
    assert image.size == (10, 20)
    assert device.calls == 2
    assert reconnects == ["screenshot.rpc_jpeg.retry"]


def test_connect_device_retries_when_accessibility_service_is_already_registered(
    monkeypatch,
):
    """连接阶段遇到已注册服务时，应在当前线程重试。"""
    controller = AdbController("127.0.0.1:5555")
    calls: list[str] = []

    def fake_connect(address: str):
        calls.append(address)
        if len(calls) == 1:
            raise u2.exceptions.AccessibilityServiceAlreadyRegisteredError("busy")
        return object()

    monkeypatch.setattr("ptcgp_auto_v2.infra.adb.u2.connect", fake_connect)
    monkeypatch.setattr("ptcgp_auto_v2.infra.adb.time.sleep", lambda _seconds: None)

    device = controller._connect_device("u2.connect")

    assert device is not None
    assert calls == ["127.0.0.1:5555", "127.0.0.1:5555"]


def test_connect_device_retries_when_uiautomator_server_quits_during_start(
    monkeypatch,
):
    """uiautomator 服务启动竞态应走连接重试。"""
    controller = AdbController("127.0.0.1:5555")
    calls: list[str] = []

    def fake_connect(address: str):
        calls.append(address)
        if len(calls) == 1:
            raise RuntimeError(
                "('server quit unexpectly', 'UiAutomation not connected')"
            )
        return object()

    monkeypatch.setattr("ptcgp_auto_v2.infra.adb.u2.connect", fake_connect)
    monkeypatch.setattr("ptcgp_auto_v2.infra.adb.time.sleep", lambda _seconds: None)

    device = controller._connect_device("u2.connect")

    assert device is not None
    assert calls == ["127.0.0.1:5555", "127.0.0.1:5555"]


def test_offline_failure_skips_restart_when_emulator_healthy(monkeypatch):
    """同设备连续离线错误达到阈值后，若实例健康检查通过则跳过重启并重置计数。"""
    address = "127.0.0.1:5675"
    restarts: list[str] = []
    AdbController._offline_failures.clear()
    controller = AdbController(address)

    monkeypatch.setattr(
        controller,
        "_should_restart_emulator",
        lambda: False,
    )
    monkeypatch.setattr(
        "ptcgp_auto_v2.infra.adb.restart_bluestacks_instance_for_device",
        lambda device_address: restarts.append(device_address) or True,
    )

    for attempt in range(ADB_CONNECT_FAIL_RESTART_THRESHOLD - 1):
        should_retry = controller.register_offline_failure(
            RuntimeError(f"device {address} not online"),
        )
        assert should_retry is False
        assert restarts == []
        assert AdbController._offline_failures[address] == attempt + 1

    # 达阈值但健康检查通过
    should_retry = controller.register_offline_failure(
        RuntimeError(f"device {address} not online"),
    )

    assert should_retry is False
    assert restarts == [], "实例健康时不应重启"
    assert AdbController._offline_failures[address] == 0, "健康时应重置计数"


def test_offline_failure_restarts_when_emulator_dead(monkeypatch):
    """同设备连续离线错误达到阈值后，若实例失活则强制重启模拟器。"""
    address = "127.0.0.1:5675"
    restarts: list[str] = []
    AdbController._offline_failures.clear()
    controller = AdbController(address)

    monkeypatch.setattr(
        controller,
        "_should_restart_emulator",
        lambda: True,
    )
    monkeypatch.setattr(
        "ptcgp_auto_v2.infra.adb.restart_bluestacks_instance_for_device",
        lambda device_address: restarts.append(device_address) or True,
    )

    # 填到阈值 - 1
    for _ in range(ADB_CONNECT_FAIL_RESTART_THRESHOLD - 1):
        controller.register_offline_failure(
            RuntimeError(f"device {address} not online"),
        )

    # 达阈值 + 实例失活
    should_retry = controller.register_offline_failure(
        RuntimeError(f"device {address} not online"),
    )

    assert should_retry is True
    assert restarts == [address]
    assert AdbController._offline_failures[address] == 0


def test_offline_failure_keeps_count_when_restart_fails(monkeypatch):
    """强制重启失败时不得清零离线计数，避免下一账号立刻重新撞墙。"""
    address = "127.0.0.1:5785"
    restarts: list[str] = []
    AdbController._offline_failures.clear()
    controller = AdbController(address)

    monkeypatch.setattr(controller, "_should_restart_emulator", lambda: True)
    monkeypatch.setattr(
        "ptcgp_auto_v2.infra.adb.restart_bluestacks_instance_for_device",
        lambda device_address: restarts.append(device_address) or False,
    )

    for _ in range(ADB_CONNECT_FAIL_RESTART_THRESHOLD - 1):
        controller.register_offline_failure(
            RuntimeError(f"device {address} not online"),
        )

    should_retry = controller.register_offline_failure(
        RuntimeError(f"device {address} not online"),
    )

    assert should_retry is False
    assert restarts == [address]
    assert AdbController._offline_failures[address] == ADB_CONNECT_FAIL_RESTART_THRESHOLD


def test_successful_connection_resets_offline_failure_count():
    """设备恢复连接后必须清理离线错误计数。"""
    address = "127.0.0.1:5675"
    AdbController._offline_failures[address] = 2

    controller = AdbController(address)
    controller._reset_connect_failures()

    assert AdbController._offline_failures[address] == 0
