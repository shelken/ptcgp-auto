# -*- coding: utf-8 -*-
"""
调试工具上下文管理

管理 ADB 连接状态和调试目录。
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from ptcgp_auto_v2.infra.adb import AdbController


# 当前 ADB 地址（全局状态）
_current_host: Optional[str] = None
_current_port: Optional[int] = None

# ADB 控制器实例（单例）
_adb_instance: Optional[AdbController] = None


def set_current_address(host: Optional[str], port: Optional[int]) -> None:
    """
    设置当前 ADB 地址

    Args:
        host: ADB 主机地址，None 则使用默认 (127.0.0.1)
        port: ADB 端口，None 则使用默认 (5555)
    """
    global _current_host, _current_port, _adb_instance

    from ptcgp_auto_v2.config.constants import DEFAULT_ADB_PORT

    _current_host = host or "127.0.0.1"
    _current_port = port or DEFAULT_ADB_PORT

    # 地址改变时重置实例
    _adb_instance = None


def get_current_address() -> tuple[str, int]:
    """
    获取当前 ADB 地址

    Returns:
        (host, port) 元组
    """
    global _current_host, _current_port

    from ptcgp_auto_v2.config.constants import DEFAULT_ADB_PORT

    if _current_host is None or _current_port is None:
        _current_host = _current_host or "127.0.0.1"
        _current_port = _current_port or DEFAULT_ADB_PORT

    return _current_host, _current_port


def get_adb() -> AdbController:
    """
    获取 ADB 控制器实例（单例）

    Returns:
        AdbController 实例
    """
    global _adb_instance

    if _adb_instance is None:
        host, port = get_current_address()
        address = f"{host}:{port}"
        _adb_instance = AdbController(address)

    return _adb_instance


def get_debug_dir() -> Path:
    """
    获取调试目录

    Returns:
        调试目录路径
    """
    _, port = get_current_address()
    debug_dir = Path(f"debug_data/{port}")
    debug_dir.mkdir(parents=True, exist_ok=True)
    return debug_dir
