"""BlueStacks Air 设备发现 - 通过进程端口"""
import subprocess
import re
from typing import List


def discover_devices() -> List[str]:
    """发现所有运行中的 BlueStacks 设备，返回 ADB 地址列表

    通过 lsof 查询 BlueStacks 进程监听的端口
    """
    # 获取 BlueStacks 进程 PID
    ps_result = subprocess.run(
        ["pgrep", "-f", "BlueStacks.*--instance"],
        capture_output=True, text=True
    )
    pids = ps_result.stdout.strip().split('\n')
    pids = [p for p in pids if p]

    if not pids:
        return []

    # 查询所有 PID 的监听端口
    devices = []
    for pid in pids:
        lsof_result = subprocess.run(
            ["lsof", "-a", "-p", pid, "-i", "-P", "-n"],
            capture_output=True, text=True
        )
        for line in lsof_result.stdout.splitlines():
            # 匹配 LISTEN 行: TCP *:5705 (LISTEN)
            if "LISTEN" in line:
                match = re.search(r'\*:(\d+)', line)
                if match:
                    port = match.group(1)
                    devices.append(f"127.0.0.1:{port}")

    return sorted(devices, key=lambda x: int(x.split(':')[1]))


if __name__ == "__main__":
    # 测试设备发现
    devices = discover_devices()
    if devices:
        print(f"发现 {len(devices)} 个设备:")
        for addr in devices:
            print(f"  - {addr}")
    else:
        print("未发现运行中的 BlueStacks 设备")
