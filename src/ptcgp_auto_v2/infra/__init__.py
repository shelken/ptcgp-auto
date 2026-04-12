# -*- coding: utf-8 -*-
"""
基础设施模块

包含 ADB 控制、OCR、模板匹配、页面检测等底层功能。
"""

from ptcgp_auto_v2.infra.adb import AdbController as AdbController
from ptcgp_auto_v2.infra.ocr import OcrEngine as OcrEngine
from ptcgp_auto_v2.infra.template import TemplateMatcher as TemplateMatcher
from ptcgp_auto_v2.infra.page_detector import PageDetector as PageDetector
from ptcgp_auto_v2.infra.account_switcher import AccountSwitcher as AccountSwitcher
from ptcgp_auto_v2.infra.account_syncer import AccountSyncer as AccountSyncer
from ptcgp_auto_v2.infra.notifier import Notifier as Notifier, get_notifier as get_notifier
