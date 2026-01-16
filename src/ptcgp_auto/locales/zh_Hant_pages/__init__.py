"""
繁体中文页面配置模块

按模式分离的页面配置，支持不同模式加载不同的页面集合。
"""

from .common import PAGES_COMMON
from .user_info import PAGES_USER_INFO
from .battle import PAGES_BATTLE
from .tutorial import PAGES_TUTORIAL
from .daily import PAGES_DAILY

__all__ = [
    "PAGES_COMMON",
    "PAGES_USER_INFO",
    "PAGES_BATTLE",
    "PAGES_TUTORIAL",
    "PAGES_DAILY",
]
