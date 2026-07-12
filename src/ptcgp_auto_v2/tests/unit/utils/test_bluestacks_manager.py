# -*- coding: utf-8 -*-
"""BlueStacks 实例重启测试。

锁定 `restart_bluestacks_instance_for_device` 的重启语义：必须杀整个实例进程树，
旧实例端口未关闭前不能启动新实例，避免进程堆积。
"""

from __future__ import annotations

from unittest.mock import patch

from ptcgp_auto_v2.utils import bluestacks_manager
from ptcgp_auto_v2.utils.bluestacks_manager import (
    restart_bluestacks_instance_for_device,
)


def test_restart_uses_pkill_to_kill_whole_instance():
    """重启时必须用 pkill -f 杀整个实例进程树，而不是只 kill 单个端口 PID。"""
    address = "127.0.0.1:5700"
    instance = "Tiramisu64_19"

    run_calls: list[list[str]] = []
    popen_calls: list[list[str]] = []

    with (
        patch.object(
            bluestacks_manager,
            "find_bluestacks_instance_by_port",
            return_value=(12345, instance),
        ),
        patch.object(
            bluestacks_manager.subprocess,
            "run",
            side_effect=lambda args, **_kw: run_calls.append(list(args)) or None,
        ),
        patch.object(
            bluestacks_manager,
            "_wait_for_port_closed",
            return_value=True,
        ),
        patch.object(
            bluestacks_manager.subprocess,
            "Popen",
            side_effect=lambda args, **_kw: popen_calls.append(list(args)) or None,
        ),
        patch.object(
            bluestacks_manager,
            "wait_for_bluestacks_port",
            return_value=True,
        ),
    ):
        result = restart_bluestacks_instance_for_device(address)

    assert result is True

    # 必须出现 pkill -f "BlueStacks.*--instance Tiramisu64_19"
    pkill_calls = [c for c in run_calls if c[:1] == ["pkill"]]
    assert pkill_calls, f"未调用 pkill，所有 run 调用: {run_calls}"
    assert pkill_calls[0] == [
        "pkill",
        "-f",
        f"BlueStacks.*--instance {instance}",
    ]

    # 不应再出现只 kill 单个 PID 的调用
    kill_pid_calls = [
        c for c in run_calls if c[:1] == ["kill"] and len(c) == 2 and c[1] == "12345"
    ]
    assert not kill_pid_calls, (
        f"不应只 kill 单 PID，应杀整个实例进程树: {run_calls}"
    )


def test_restart_aborts_when_port_not_closed():
    """旧实例端口未关闭时必须放弃启动新实例，返回 False。"""
    address = "127.0.0.1:5700"
    instance = "Tiramisu64_20"
    popen_calls: list[list[str]] = []

    with (
        patch.object(
            bluestacks_manager,
            "find_bluestacks_instance_by_port",
            return_value=(12345, instance),
        ),
        patch.object(
            bluestacks_manager.subprocess,
            "run",
        ),
        patch.object(
            bluestacks_manager,
            "_wait_for_port_closed",
            return_value=False,
        ),
        patch.object(
            bluestacks_manager.subprocess,
            "Popen",
            side_effect=lambda args, **_kw: popen_calls.append(list(args)) or None,
        ),
        patch.object(
            bluestacks_manager,
            "wait_for_bluestacks_port",
        ),
    ):
        result = restart_bluestacks_instance_for_device(address)

    assert result is False
    assert popen_calls == [], "端口未关闭时不应启动新实例"


def test_restart_starts_new_instance_after_port_closed():
    """旧实例端口关闭后必须启动新实例并等待端口就绪。"""
    address = "127.0.0.1:5700"
    instance = "Tiramisu64_21"
    popen_calls: list[list[str]] = []

    with (
        patch.object(
            bluestacks_manager,
            "find_bluestacks_instance_by_port",
            return_value=(12345, instance),
        ),
        patch.object(
            bluestacks_manager.subprocess,
            "run",
        ),
        patch.object(
            bluestacks_manager,
            "_wait_for_port_closed",
            return_value=True,
        ),
        patch.object(
            bluestacks_manager.subprocess,
            "Popen",
            side_effect=lambda args, **_kw: popen_calls.append(list(args)) or None,
        ),
        patch.object(
            bluestacks_manager,
            "wait_for_bluestacks_port",
            return_value=True,
        ),
    ):
        result = restart_bluestacks_instance_for_device(address)

    assert result is True
    assert len(popen_calls) == 1
    assert "--instance" in popen_calls[0]
    assert instance in popen_calls[0]


def test_restart_force_kills_when_sigterm_leaves_port_open():
    """SIGTERM 后端口仍在，必须 pkill -9 / kill -9，端口关了再启动。"""
    address = "127.0.0.1:5785"
    instance = "Tiramisu64_23"
    run_calls: list[list[str]] = []
    popen_calls: list[list[str]] = []
    wait_returns = iter([False, True])  # soft 失败，hard 成功

    with (
        patch.object(
            bluestacks_manager,
            "find_bluestacks_instance_by_port",
            return_value=(98337, instance),
        ),
        patch.object(
            bluestacks_manager.subprocess,
            "run",
            side_effect=lambda args, **_kw: run_calls.append(list(args)) or None,
        ),
        patch.object(
            bluestacks_manager,
            "_wait_for_port_closed",
            side_effect=lambda *_a, **_k: next(wait_returns),
        ),
        patch.object(
            bluestacks_manager,
            "find_bluestacks_pid_by_port",
            return_value=98337,
        ),
        patch.object(
            bluestacks_manager.subprocess,
            "Popen",
            side_effect=lambda args, **_kw: popen_calls.append(list(args)) or None,
        ),
        patch.object(
            bluestacks_manager,
            "wait_for_bluestacks_port",
            return_value=True,
        ),
        patch.object(bluestacks_manager.time, "sleep", return_value=None),
    ):
        result = restart_bluestacks_instance_for_device(address)

    assert result is True
    pkill_calls = [c for c in run_calls if c[:1] == ["pkill"]]
    assert ["pkill", "-f", f"BlueStacks.*--instance {instance}"] in pkill_calls
    assert ["pkill", "-9", "-f", f"BlueStacks.*--instance {instance}"] in pkill_calls
    assert ["kill", "-9", "98337"] in run_calls
    assert len(popen_calls) == 1


def test_restart_aborts_when_force_kill_still_leaves_port_open():
    """SIGKILL 后端口仍在，必须放弃启动。"""
    address = "127.0.0.1:5785"
    instance = "Tiramisu64_23"
    popen_calls: list[list[str]] = []

    with (
        patch.object(
            bluestacks_manager,
            "find_bluestacks_instance_by_port",
            return_value=(98337, instance),
        ),
        patch.object(bluestacks_manager.subprocess, "run"),
        patch.object(
            bluestacks_manager,
            "_wait_for_port_closed",
            return_value=False,
        ),
        patch.object(
            bluestacks_manager,
            "find_bluestacks_pid_by_port",
            return_value=98337,
        ),
        patch.object(
            bluestacks_manager.subprocess,
            "Popen",
            side_effect=lambda args, **_kw: popen_calls.append(list(args)) or None,
        ),
        patch.object(bluestacks_manager.time, "sleep", return_value=None),
    ):
        result = restart_bluestacks_instance_for_device(address)

    assert result is False
    assert popen_calls == []
