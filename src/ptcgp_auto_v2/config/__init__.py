# -*- coding: utf-8 -*-
"""
配置模块

包含运行时配置和页面规则。
"""

from ptcgp_auto_v2.config.settings import Settings, get_settings
from ptcgp_auto_v2.config.pages.common import COMMON_PAGES

__all__ = [
    "Settings",
    "get_settings",
    "COMMON_PAGES",
]
