# -*- coding: utf-8 -*-
"""日志来源解析工具"""

from ptcgp_auto_v2.utils.bluestacks_manager import (
    extract_port_from_address,
    list_manageable_instances,
)


def resolve_log_device(
    address: str,
    auto_scale_instance_prefix: str,
) -> tuple[str, str]:
    """
    解析日志设备显示名与颜色键。

    Returns:
        (device_display, color_key)
    """
    port = extract_port_from_address(address)
    if port is None:
        return "----", "----"

    port_str = str(port)
    if not auto_scale_instance_prefix:
        return port_str, port_str

    manageable_map = list_manageable_instances(prefix=auto_scale_instance_prefix)
    auto_instance = manageable_map.get(port)
    if auto_instance is None:
        return port_str, port_str

    _, display_name = auto_instance
    return display_name, port_str
