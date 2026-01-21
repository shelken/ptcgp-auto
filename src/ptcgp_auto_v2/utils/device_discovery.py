# -*- coding: utf-8 -*-
"""
设备发现工具

自动发现当前运行的 BlueStacks 设备端口。
"""

import logging
import re
import subprocess
from typing import List

logger = logging.getLogger(__name__)


def discover_devices() -> List[str]:
    """发现所有运行中的 BlueStacks 设备地址"""
    ps_result = subprocess.run(
        ["pgrep", "-f", "BlueStacks.*--instance"],
        capture_output=True,
        text=True,
        check=False,
    )
    pids = [pid for pid in ps_result.stdout.strip().split("\n") if pid]
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
        for line in lsof_result.stdout.splitlines():
            if "LISTEN" in line:
                match = re.search(r"\*:(\d+)", line)
                if match:
                    port = match.group(1)
                    devices.append(f"127.0.0.1:{port}")

    devices = sorted(devices, key=lambda addr: int(addr.split(":")[1]))
    if devices:
        logger.info(f"发现 {len(devices)} 个 BlueStacks 设备")
    return devices
