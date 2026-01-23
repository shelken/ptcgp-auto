# -*- coding: utf-8 -*-
"""
基础手势与点击工具
"""

import logging
from typing import Callable, Optional, Tuple

from ptcgp_auto_v2.core.task_base import ActionResult

logger = logging.getLogger(__name__)

# ============================================================
# 常量定义（基于 1080x1920 基准分辨率的像素值）
# 使用时通过 adb.scaled_x/scaled_y 缩放到当前分辨率
# ============================================================

# 开包滑动坐标（从左到右）
BASE_SWIPE_PACK_START_X = 54   # 1080 * 0.05
BASE_SWIPE_PACK_END_X = 1026   # 1080 * 0.95

# 卡牌上滑坐标（从下到上）
BASE_SWIPE_CARD_START_Y = 1152  # 1920 * 0.6
BASE_SWIPE_CARD_END_Y = 384     # 1920 * 0.2


def tap_template(
    adb, page_detector, template_name: str, wait: float = 1.0
) -> Optional[ActionResult]:
    """点击指定模板位置"""
    box = page_detector.find_template(template_name)
    if not box:
        return None
    adb.tap_center(box)
    logger.debug(f"点击模板: {template_name}")
    return ActionResult.ok(wait=wait)


def tap_center(adb, wait: float = 1.0) -> ActionResult:
    """点击屏幕中心"""
    adb.tap(adb.screen_width // 2, adb.screen_height // 2)
    return ActionResult.ok(wait=wait)


def tap_right_side(adb, ratio: float = 0.75, wait: float = 1.0) -> ActionResult:
    """点击屏幕右侧区域"""
    tap_x = int(adb.screen_width * ratio)
    tap_y = adb.screen_height // 2
    adb.tap(tap_x, tap_y)
    return ActionResult.ok(wait=wait)


def press_back(adb, wait: float = 1.0) -> ActionResult:
    """按返回键"""
    adb.press_back()
    return ActionResult.wait(wait)


def tap_text(
    adb,
    ocr_results: list[dict],
    patterns: list[str],
    wait: float = 1.0,
    exact: bool = False,
) -> Optional[ActionResult]:
    """按文本列表匹配点击

    Args:
        adb: ADB 控制器
        ocr_results: OCR 识别结果
        patterns: 待匹配的文本列表
        wait: 点击后等待时间
        exact: 是否精确匹配（默认 False 为包含匹配）
    """
    for pattern in patterns:
      for item in ocr_results:
        text = "".join(item["text"].lower().split())
        pattern_normalized = "".join(pattern.lower().split())
        if exact:
            matched = pattern_normalized == text
        else:
            matched = pattern_normalized in text
        if matched:
            adb.tap_center(item["box"])
            logger.debug(f"点击文字: {pattern}")
            return ActionResult.ok(wait=wait)
    return None


def tap_by_priority(
    adb,
    page_detector,
    ocr_results: list[dict],
    patterns: list[str],
    template_name: Optional[str] = None,
    wait: float = 1.0,
) -> Optional[ActionResult]:
    """按模板优先、文字次之执行点击"""
    if template_name:
        result = tap_template(adb, page_detector, template_name, wait=wait)
        if result:
            return result

    result = tap_text(adb, ocr_results, patterns, wait=wait)
    if result:
        return result

    return None


def tap_template_or_text(
    adb,
    page_detector,
    ocr_results: list[dict],
    template_name: Optional[str],
    patterns: list[str],
    wait: float = 1.0,
) -> Optional[ActionResult]:
    """模板优先、文本兜底的点击（统一日志与等待）"""
    result = tap_by_priority(
        adb,
        page_detector,
        ocr_results,
        patterns,
        template_name=template_name,
        wait=wait,
    )
    if result:
        return result

    if template_name:
        logger.debug(f"未匹配模板或文本: {template_name}")
    return None


def tap_template_or_fallback(
    adb,
    page_detector,
    template_name: str,
    fallback_action: Callable[[], ActionResult],
    wait: float = 1.0,
) -> ActionResult:
    """模板点击优先，否则执行回退动作"""
    result = tap_template(adb, page_detector, template_name, wait=wait)
    if result:
        return result
    return fallback_action()


def tap_template_with_scale(
    page_detector,
    template_name: str,
    scale: float,
    threshold: float = 0.7,
    wait: float = 1.0,
) -> Optional[ActionResult]:
    """按缩放比例匹配模板并点击"""
    match = page_detector.find_template_with_scale(
        template_name, scale=scale, threshold=threshold
    )
    if not match:
        return None
    page_detector.adb.tap_center(match.box)
    return ActionResult.ok(wait=wait)


def scroll_until_template(
    page_detector,
    template_name: str,
    scale: float,
    threshold: float,
    max_attempts: int,
    swipe_ratio: float,
    wait: float,
) -> Optional[ActionResult]:
    """循环上滑直到命中模板或达到上限"""
    last_signature = None
    for attempt in range(max_attempts):
        logger.info(f"  -> 第 {attempt + 1} 次上滑查找模板: {template_name}")
        swipe_up(page_detector.adb, ratio=swipe_ratio, wait=wait)
        screenshot, ocr_results = page_detector.capture()
        if not screenshot:
            continue
        match = page_detector.find_template_with_scale(
            template_name, scale=scale, threshold=threshold, screenshot=screenshot
        )
        if match:
            page_detector.adb.tap_center(match.box)
            return ActionResult.ok(wait=1.0)
        current_signature = "|".join(sorted([item["text"] for item in ocr_results]))
        if last_signature and current_signature == last_signature:
            logger.warning("  -> 滑动到底部，未找到目标模板")
            break
        last_signature = current_signature
    return None


def cycle_until_template(
    page_detector,
    template_name: str,
    scale: float,
    threshold: float,
    max_attempts: int,
    wait: float,
) -> Optional[ActionResult]:
    """循环点击右侧切换直到命中模板或回到起点"""
    screenshot, ocr_results = page_detector.get_last_page_context()
    if not screenshot:
        return None
    first_signature = "|".join(sorted([item["text"] for item in ocr_results]))
    for attempt in range(max_attempts):
        logger.info(f"  -> 第 {attempt + 1} 次切换子包")
        tap_right_side(page_detector.adb, wait=wait)
        screenshot, ocr_results = page_detector.capture()
        if not screenshot:
            continue
        match = page_detector.find_template_with_scale(
            template_name, scale=scale, threshold=threshold, screenshot=screenshot
        )
        if match:
            page_detector.adb.tap_center(match.box)
            return ActionResult.ok(wait=1.0)
        current_signature = "|".join(sorted([item["text"] for item in ocr_results]))
        if current_signature == first_signature:
            logger.warning("  -> 循环一圈，未找到目标模板")
            break
    return None


def click_confirm(
    adb, page_detector, ocr_results: list[dict], patterns: list[str]
) -> ActionResult:
    """点击确认按钮（模板优先）"""
    result = tap_by_priority(
        adb,
        page_detector,
        ocr_results,
        patterns,
        template_name="btn_continue.png",
        wait=1.0,
    )
    if result:
        return result
    return tap_center(adb, wait=1.0)


def click_continue(
    adb, page_detector, ocr_results: list[dict], patterns: list[str]
) -> ActionResult:
    """点击继续按钮（模板优先）"""
    result = tap_by_priority(
        adb,
        page_detector,
        ocr_results,
        patterns,
        template_name="btn_continue.png",
        wait=1.0,
    )
    if result:
        return result
    return tap_center(adb, wait=1.0)


def click_close(
    adb, page_detector, ocr_results: list[dict], patterns: list[str]
) -> Optional[ActionResult]:
    """点击关闭按钮（模板优先）"""
    return tap_by_priority(
        adb,
        page_detector,
        ocr_results,
        patterns,
        template_name="btn_close",
        wait=1.0,
    )


def tap_home_icon(adb, page_detector, wait: float = 1.0) -> ActionResult:
    """点击主页图标"""
    result = tap_template(adb, page_detector, "icon_home", wait=wait)
    if result:
        return result
    return ActionResult.wait(wait)


def navigate_back(
    adb,
    page_detector,
    ocr_results: list[dict],
    patterns: list[str],
) -> ActionResult:
    """按返回按钮优先级返回"""
    result = tap_by_priority(
        adb,
        page_detector,
        ocr_results,
        patterns,
        template_name="btn_back",
        wait=1.0,
    )
    if result:
        return result

    return press_back(adb, wait=1.0)


def swipe_up(adb, ratio: float = 0.26, wait: float = 1.0) -> ActionResult:
    """向上滑动"""
    adb.swipe_up(ratio=ratio)
    return ActionResult.ok(wait=wait)


def swipe(
    adb,
    start: Tuple[int, int],
    end: Tuple[int, int],
    duration: int = 300,
    wait: float = 1.0,
) -> ActionResult:
    """执行自定义滑动"""
    adb.swipe(*start, *end, duration)
    return ActionResult.ok(wait=wait)


def long_press(
    adb, point: Tuple[int, int], duration: int = 3000, wait: float = 1.0
) -> ActionResult:
    """长按指定位置"""
    adb.long_press(point[0], point[1], duration)
    return ActionResult.ok(wait=wait)


def long_press_text(
    adb,
    ocr_results: list[dict],
    patterns: list[str],
    duration: int = 3000,
    wait: float = 1.0,
) -> Optional[ActionResult]:
    """按文本列表匹配长按"""
    for pattern in patterns:
        for item in ocr_results:
            text = "".join(item["text"].lower().split())
            if "".join(pattern.lower().split()) in text:
                box = item["box"]
                cx = (box[0] + box[2]) // 2
                cy = (box[1] + box[3]) // 2
                adb.long_press(cx, cy, duration)
                logger.debug(f"长按文字: {pattern} @ ({cx}, {cy})")
                return ActionResult.ok(wait=wait)
    return None


def center_point(adb) -> Tuple[int, int]:
    """获取屏幕中心坐标"""
    return adb.screen_width // 2, adb.screen_height // 2


def swipe_pack_coords(adb) -> Tuple[Tuple[int, int], Tuple[int, int]]:
    """获取开包滑动坐标（从左到右）"""
    start_x = adb.scaled_x(BASE_SWIPE_PACK_START_X)
    end_x = adb.scaled_x(BASE_SWIPE_PACK_END_X)
    y = adb.screen_height // 2
    return (start_x, y), (end_x, y)


def swipe_card_coords(adb) -> Tuple[Tuple[int, int], Tuple[int, int]]:
    """获取卡牌上滑坐标（从下到上）"""
    x = adb.screen_width // 2
    start_y = adb.scaled_y(BASE_SWIPE_CARD_START_Y)
    end_y = adb.scaled_y(BASE_SWIPE_CARD_END_Y)
    return (x, start_y), (x, end_y)
