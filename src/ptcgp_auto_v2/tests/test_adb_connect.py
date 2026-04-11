# -*- coding: utf-8 -*-
"""ADB 连接路径测试。

这个文件负责验证 ADB 控制器的连接阶段不会把 `u2.connect` 放进后台线程。之前连接阶段复用了底层调用超时包装，导致 `u2.connect` 在后台线程里超时卡死。现在锁定连接动作必须在调用线程执行，其他设备调用仍保持原来的 failfast 包装。
"""

from __future__ import annotations

import threading

import uiautomator2 as u2

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
