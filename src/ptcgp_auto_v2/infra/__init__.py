# -*- coding: utf-8 -*-
"""
基础设施模块

包含 ADB 控制、OCR、模板匹配、页面检测等底层功能。
"""

from ptcgp_auto_v2.infra.adb import AdbController
from ptcgp_auto_v2.infra.ocr import OcrEngine
from ptcgp_auto_v2.infra.template import TemplateMatcher
from ptcgp_auto_v2.infra.page_detector import PageDetector
from ptcgp_auto_v2.infra.account_switcher import AccountSwitcher
from ptcgp_auto_v2.infra.account_syncer import AccountSyncer, get_current_account
from ptcgp_auto_v2.infra.notifier import Notifier, get_notifier

__all__ = [
    "AdbController",
    "OcrEngine",
    "TemplateMatcher",
    "PageDetector",
    "AccountSwitcher",
    "AccountSyncer",
    "get_current_account",
    "Notifier",
    "get_notifier",
]
