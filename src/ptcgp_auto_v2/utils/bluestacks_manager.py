# -*- coding: utf-8 -*-
"""
BlueStacks Air 实例管理工具
"""

from __future__ import annotations

import logging
import re
import subprocess
import time
from typing import List, Optional, Tuple

logger = logging.getLogger(__name__)

DEFAULT_BLUESTACKS_BIN = "/Applications/BlueStacks.app/Contents/MacOS/BlueStacks"


def parse_bluestacks_instance(command: str) -> Optional[str]:
    """从命令行中解析 --instance 参数"""
    match = re.search(r"--instance\s+(\S+)", command)
    if match:
        return match.group(1)
    return None


def _extract_port_from_address(address: str) -> Optional[int]:
    if not address:
        return None
    if ":" not in address:
        return None
    try:
        return int(address.rsplit(":", 1)[1])
    except ValueError:
        return None


def _parse_pid_from_lsof(output: str) -> Optional[int]:
    """从 lsof 输出中解析 PID"""
    for line in output.splitlines():
        if not line or line.startswith("COMMAND"):
            continue
        if "LISTEN" not in line:
            continue
        parts = line.split()
        if len(parts) < 2:
            continue
        pid_str = parts[1]
        if pid_str.isdigit():
            return int(pid_str)
    return None


def find_bluestacks_pid_by_port(port: int) -> Optional[int]:
    """通过端口查找 BlueStacks 进程 PID"""
    result = subprocess.run(
        ["lsof", "-n", "-P", f"-iTCP:{port}", "-sTCP:LISTEN"],
        capture_output=True,
        text=True,
        check=False,
    )
    pid = _parse_pid_from_lsof(result.stdout or "")
    if pid is None:
        logger.warning("未找到监听端口 %s 的进程", port)
    return pid


def find_bluestacks_instance_by_port(port: int) -> Optional[Tuple[int, str]]:
    """通过端口查找 BlueStacks 实例名"""
    pid = find_bluestacks_pid_by_port(port)
    if pid is None:
        return None

    ps_result = subprocess.run(
        ["ps", "-p", str(pid), "-o", "command="],
        capture_output=True,
        text=True,
        check=False,
    )
    command = (ps_result.stdout or "").strip()
    instance = parse_bluestacks_instance(command)
    if not instance:
        logger.warning("未解析到 BlueStacks 实例名，PID=%s", pid)
        return None
    return pid, instance


def restart_bluestacks_instance_for_device(
    device_address: str,
    bin_path: str = DEFAULT_BLUESTACKS_BIN,
) -> bool:
    """重启当前设备对应的 BlueStacks 实例"""
    port = _extract_port_from_address(device_address)
    if port is None:
        logger.warning("无法解析设备端口: %s", device_address)
        return False

    resolved = find_bluestacks_instance_by_port(port)
    if not resolved:
        logger.warning("无法找到端口 %s 对应的实例", port)
        return False

    pid, instance = resolved
    logger.info("准备重启 BlueStacks 实例: %s (PID=%s)", instance, pid)

    subprocess.run(["kill", str(pid)], check=False)
    time.sleep(1.5)

    subprocess.Popen(
        [bin_path, "--instance", instance],
        start_new_session=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    logger.info("已启动 BlueStacks 实例: %s", instance)
    return True


def discover_bluestacks_devices() -> List[str]:
    """发现所有运行中的 BlueStacks 设备地址"""
    ps_result = subprocess.run(
        ["pgrep", "-f", "BlueStacks.*--instance"],
        capture_output=True,
        text=True,
        check=False,
    )
    pids = [pid for pid in (ps_result.stdout or "").strip().split("\n") if pid]
    if not pids:
        return []

    devices: List[str] = []
    for pid in pids:
        lsof_result = subprocess.run(
            ["lsof", "-a", "-p", pid, "-i", "-P", "-n"],
            capture_output=True,
            text=True,
            check=False,
        )
        for line in (lsof_result.stdout or "").splitlines():
            if "LISTEN" not in line:
                continue
            match = re.search(r"\*:(\d+)", line)
            if match:
                port = match.group(1)
                devices.append(f"127.0.0.1:{port}")

    devices = sorted(devices, key=lambda addr: int(addr.split(":")[1]))
    if devices:
        logger.info("发现 %s 个 BlueStacks 设备", len(devices))
    return devices


__all__ = [
    "DEFAULT_BLUESTACKS_BIN",
    "parse_bluestacks_instance",
    "find_bluestacks_pid_by_port",
    "find_bluestacks_instance_by_port",
    "restart_bluestacks_instance_for_device",
    "discover_bluestacks_devices",
]
