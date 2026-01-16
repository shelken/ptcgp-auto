"""
Root 检测模块

检测 ADB 设备是否拥有 root 权限。
"""

import subprocess
from typing import List, Tuple

from ..logger import get_logger

logger = get_logger(__name__)

# Root 检测超时时间（秒）
ROOT_CHECK_TIMEOUT = 5


def is_rooted(device_address: str, timeout: int = ROOT_CHECK_TIMEOUT) -> bool:
    """
    检查设备是否已 root

    通过尝试执行 su 命令来判断设备是否拥有 root 权限。

    Args:
        device_address: 设备地址（如 "127.0.0.1:5555"）
        timeout: 命令超时时间（秒）

    Returns:
        True 如果设备已 root，否则 False
    """
    try:
        result = subprocess.run(
            ["adb", "-s", device_address, "shell", "su", "-c", "echo 1"],
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        # 如果成功执行且输出为 "1"，则设备已 root
        is_root = result.stdout.strip() == "1"
        if is_root:
            logger.debug(f"设备 {device_address} 已 root")
        else:
            logger.debug(
                f"设备 {device_address} 未 root: stdout={result.stdout!r}, "
                f"stderr={result.stderr!r}"
            )
        return is_root
    except subprocess.TimeoutExpired:
        logger.warning(f"设备 {device_address} root 检测超时")
        return False
    except subprocess.SubprocessError as e:
        logger.warning(f"设备 {device_address} root 检测失败: {e}")
        return False
    except FileNotFoundError:
        logger.error("未找到 adb 命令，请确保 ADB 已安装并在 PATH 中")
        return False


def filter_rooted_devices(device_addresses: List[str]) -> Tuple[List[str], List[str]]:
    """
    过滤出已 root 的设备

    Args:
        device_addresses: 设备地址列表

    Returns:
        (已 root 的设备列表, 未 root 的设备列表)
    """
    rooted = []
    not_rooted = []

    for addr in device_addresses:
        if is_rooted(addr):
            rooted.append(addr)
        else:
            not_rooted.append(addr)

    if not_rooted:
        logger.warning(
            f"以下设备未 root，将被排除: {', '.join(not_rooted)}"
        )

    logger.info(f"已 root 设备数量: {len(rooted)}/{len(device_addresses)}")
    return rooted, not_rooted


def check_root_with_magisk(device_address: str) -> Tuple[bool, str]:
    """
    检查设备 root 状态，同时检测 Magisk

    Args:
        device_address: 设备地址

    Returns:
        (是否 root, 检测方法描述)
    """
    # 方法 1: 尝试 su -c id
    try:
        result = subprocess.run(
            ["adb", "-s", device_address, "shell", "su", "-c", "id"],
            capture_output=True,
            text=True,
            timeout=ROOT_CHECK_TIMEOUT,
        )
        if "uid=0" in result.stdout:
            return True, "su"
    except (subprocess.TimeoutExpired, subprocess.SubprocessError):
        pass

    # 方法 2: 检查 Magisk
    try:
        result = subprocess.run(
            ["adb", "-s", device_address, "shell", "magisk", "-v"],
            capture_output=True,
            text=True,
            timeout=ROOT_CHECK_TIMEOUT,
        )
        if result.stdout.strip() and ":" in result.stdout:
            # Magisk 版本格式如 "27.0:MAGISK"
            # 进一步验证是否真正可用
            result2 = subprocess.run(
                ["adb", "-s", device_address, "shell", "su", "-c", "echo root_ok"],
                capture_output=True,
                text=True,
                timeout=ROOT_CHECK_TIMEOUT,
            )
            if "root_ok" in result2.stdout:
                return True, "magisk"
            else:
                return False, "magisk_not_ready"
    except (subprocess.TimeoutExpired, subprocess.SubprocessError):
        pass

    # 方法 3: 检查 su 二进制是否存在
    try:
        result = subprocess.run(
            [
                "adb",
                "-s",
                device_address,
                "shell",
                "ls /sbin/su /system/bin/su /system/xbin/su 2>/dev/null",
            ],
            capture_output=True,
            text=True,
            timeout=ROOT_CHECK_TIMEOUT,
        )
        if result.stdout.strip():
            return False, "su_exists_but_not_working"
    except (subprocess.TimeoutExpired, subprocess.SubprocessError):
        pass

    return False, "not_rooted"
