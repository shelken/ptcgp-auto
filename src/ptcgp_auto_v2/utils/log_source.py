# -*- coding: utf-8 -*-
"""
日志来源解析工具
"""

from ptcgp_auto_v2.utils.bluestacks_manager import list_manageable_instances


def extract_port(address: str) -> str:
    """从设备地址提取端口。"""
    if ":" not in address:
        return "----"

    port = address.rsplit(":", 1)[-1].strip()
    if not port.isdigit():
        return "----"
    return port


def resolve_log_device(
    address: str,
    auto_scale_instance_prefix: str,
) -> tuple[str, str]:
    """
    解析日志设备显示名与颜色键。

    Returns:
        (device_display, color_key)
    """
    port = extract_port(address)
    if port == "----" or not auto_scale_instance_prefix:
        return port, port

    manageable_map = list_manageable_instances(prefix=auto_scale_instance_prefix)
    auto_instance = manageable_map.get(int(port))
    if auto_instance is None:
        return port, port

    _, display_name = auto_instance
    return display_name, port
