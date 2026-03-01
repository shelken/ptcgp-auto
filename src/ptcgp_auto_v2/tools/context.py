"""
调试工具上下文
"""

from typing import Optional

from ptcgp_auto import config
from ptcgp_auto.adb_controller import AdbController
from ptcgp_auto.utils import get_data_dir

_current_host: Optional[str] = None
_current_port: Optional[int] = None


def set_current_address(host: Optional[str], port: Optional[int]) -> None:
    """设置当前连接地址"""
    global _current_host, _current_port
    _current_host = host
    _current_port = port


def get_current_host() -> Optional[str]:
    """获取当前主机"""
    return _current_host


def get_current_port() -> Optional[int]:
    """获取当前端口"""
    return _current_port


def get_adb() -> AdbController:
    """获取 ADB 控制器"""
    return AdbController(_current_host, _current_port)


def get_debug_dir():
    """获取当前连接的调试目录"""
    port = _current_port or config.ADB_PORT
    return get_data_dir(port)
