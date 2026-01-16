"""
XML 账号操作模块

提供账号 XML 文件的提取和注入功能。
"""

from .extractor import AccountExtractor, extract_account
from .injector import AccountInjector, inject_account

__all__ = [
    "AccountExtractor",
    "AccountInjector",
    "extract_account",
    "inject_account",
]
