# -*- coding: utf-8 -*-
"""
设备发现工具

自动发现当前运行的 BlueStacks 设备端口。
"""

import logging
from typing import List

from ptcgp_auto_v2.utils.bluestacks_manager import discover_bluestacks_devices

logger = logging.getLogger(__name__)


def discover_devices() -> List[str]:
    """发现所有运行中的 BlueStacks 设备地址"""
    return discover_bluestacks_devices()
