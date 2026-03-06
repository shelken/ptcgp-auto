# -*- coding: utf-8 -*-
"""
开包流程通用动作工具。

沉淀多个任务可复用的无状态动作：滑动开包、图鉴上滑、长按跳过、点击继续。
"""

import logging
from typing import Optional

from ptcgp_auto_v2.config.constants import SWIPE_STEPS_OPEN, SWIPE_STEPS_REGISTER
from ptcgp_auto_v2.locales import get_text_patterns
from ptcgp_auto_v2.utils.action_result import ActionResult
from ptcgp_auto_v2.utils.gesture import (
    long_press_text,
    swipe,
    swipe_card_coords,
    swipe_pack_coords,
    tap_continue,
)

logger = logging.getLogger(__name__)


def swipe_open_pack(adb, wait: float = 2.5) -> ActionResult:
    """执行从左到右滑动开包动作。"""
    start, end = swipe_pack_coords(adb)
    logger.debug("  -> 从左往右滑动开包")
    return swipe(adb, start, end, steps=SWIPE_STEPS_OPEN, wait=wait)


def swipe_card_register(adb, wait: float = 1.0) -> ActionResult:
    """执行图鉴登录页的向上滑动动作。"""
    start, end = swipe_card_coords(adb)
    logger.debug("  -> 向上滑动卡牌登录图鉴")
    return swipe(adb, start, end, steps=SWIPE_STEPS_REGISTER, wait=wait)


def long_press_opening_card(
    adb,
    ocr_results: list[dict],
    wait: float = 3.0,
) -> Optional[ActionResult]:
    """在开包展示页长按文字以跳过动画。"""
    patterns = get_text_patterns("long_press")
    result = long_press_text(adb, ocr_results, patterns, wait=wait)
    if result:
        logger.debug("  -> 长按文字跳过卡牌展示")
    return result


def tap_opening_continue(
    adb,
    ocr_results: list[dict],
    wait: float = 1.5,
) -> ActionResult:
    """在开包结果页点击继续（无文本时兜底点中心）。"""
    logger.info("  -> 点击继续")
    return tap_continue(adb, ocr_results, wait=wait)
