# -*- coding: utf-8 -*-
"""
选卡流程共用助手
"""

from ptcgp_auto_v2.core.task_base import ActionResult
from ptcgp_auto_v2.utils.gesture import tap

# ============================================================
# 常量定义（基于 1080x1920 基准分辨率）
# ============================================================

BASE_FAVORITE_CARD_TAP_Y = 740


def tap_favorite_card(adb, wait: float = 1.0) -> ActionResult:
    """点击选卡页的卡牌区域"""
    tap_x = adb.center_x()
    tap_y = adb.scaled_y(BASE_FAVORITE_CARD_TAP_Y)
    return tap(adb, tap_x, tap_y, wait=wait)
