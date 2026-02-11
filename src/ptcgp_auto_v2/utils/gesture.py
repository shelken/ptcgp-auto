# -*- coding: utf-8 -*-
"""
基础手势与点击工具
"""

import logging
import math
import time
from typing import Callable, Optional, Tuple

from src.ptcgp_auto_v2.infra.adb import AdbController

Box = tuple[int, int, int, int]

from ptcgp_auto_v2.config.constants import (
    DEFAULT_LONG_PRESS_STEPS,
    DEFAULT_TEMPLATE_THRESHOLD,
    SWIPE_STEPS_BASE_RATIO,
    SWIPE_STEPS_BASE_VALUE,
    SWIPE_STEPS_MAX,
    SWIPE_STEPS_MIN,
    SWIPE_STEPS_SCROLL,
)
from ptcgp_auto_v2.locales import get_text_patterns
from ptcgp_auto_v2.utils.action_result import ActionResult

logger = logging.getLogger(__name__)

# ============================================================
# 常量定义（基于 1080x1920 基准分辨率的像素值）
# 使用时通过 adb.scaled_x/scaled_y 缩放到当前分辨率
# ============================================================

# 开包滑动坐标（从左到右）
BASE_SWIPE_PACK_START_X = 54  # 1080 * 0.05
BASE_SWIPE_PACK_END_X = 1126  # 1080 * 0.95
BASE_SWIPE_PACK_END_Y = 1190  # 1920 * 0.62

# 卡牌上滑坐标（从下到上）
BASE_SWIPE_CARD_START_Y = 1152  # 1920 * 0.6
BASE_SWIPE_CARD_END_Y = 384  # 1920 * 0.2

# 通用列表滚动距离（基于 1920 高度）
BASE_SCROLL_DISTANCE_DEFAULT = 500


def tap_template(
    adb: AdbController,
    page_detector,
    template_name: str,
    threshold=DEFAULT_TEMPLATE_THRESHOLD,
    wait: float = 1.0,
) -> Optional[ActionResult]:
    """点击指定模板位置"""
    box = page_detector.find_template(template_name, threshold=threshold)
    if not box:
        return None
    adb.tap_center(box)
    logger.debug(f"点击模板: {template_name}")
    return ActionResult.ok(wait=wait)


def tap(adb: AdbController, x: int, y: int, wait: float = 1.0) -> ActionResult:
    """点击指定坐标"""
    adb.tap(x, y)
    return ActionResult.ok(wait=wait)


def perform_tap(adb: AdbController, x: int, y: int, wait: float = 1.0) -> ActionResult:
    """执行点击动作并返回结果"""
    return tap(adb, x, y, wait=wait)


def tap_box(adb: AdbController, box: Box, wait: float = 1.0) -> ActionResult:
    """点击边界框中心"""
    adb.tap_center(box)
    return ActionResult.ok(wait=wait)


def tap_center(adb: AdbController, wait: float = 1.0) -> ActionResult:
    """点击屏幕中心"""
    return tap(adb, adb.center_x(), adb.center_y(), wait=wait)


def quick_tap(
    adb: AdbController,
    x: Optional[int] = None,
    y: Optional[int] = None,
    times: int = 3,
    tap_points: Optional[list[tuple[int, int]]] = None,
    wait: float = 0.1,
) -> ActionResult:
    """
    快速点击指定位置多次

    Args:
        adb: ADB 控制器
        x: 点击 X 坐标（默认屏幕中心）
        y: 点击 Y 坐标（默认屏幕中心）
        times: 点击轮次
        tap_points: 点位列表，传入后按列表顺序点击（忽略 x/y）
        wait: 点击后等待时间
    """
    points = tap_points
    if not points:
        if x is None:
            x = adb.center_x()
        if y is None:
            y = adb.center_y()
        points = [(x, y)]

    for i in range(times):
        for point_x, point_y in points:
            adb.tap(point_x, point_y)
        if i < times - 1:
            # 快速点击之间短暂等待
            time.sleep(0.05)

    # logger.debug(f"快速点击 {times} 次: ({x}, {y})")
    return ActionResult.ok(wait=wait)


def tap_right_side(
    adb: AdbController, ratio: float = 0.75, wait: float = 1.0
) -> ActionResult:
    """点击屏幕右侧区域"""
    tap_x = int(adb.screen_width * ratio)
    tap_y = adb.center_y()
    return tap(adb, tap_x, tap_y, wait=wait)


def press_back(adb: AdbController, wait: float = 1.0) -> ActionResult:
    """按返回键"""
    adb.press_back()
    return ActionResult.wait(wait)


def normalize_text(text: str) -> str:
    """Normalize text for OCR matching."""
    return "".join(text.lower().split())


def is_text_visible(
    ocr_results: list[dict],
    patterns: list[str],
    exact: bool = False,
) -> bool:
    """Check if any pattern is visible in OCR results."""
    for pattern in patterns:
        pattern_normalized = normalize_text(pattern)
        for item in ocr_results:
            text = normalize_text(item["text"])
            if exact:
                matched = pattern_normalized == text
            else:
                matched = pattern_normalized in text
            if matched:
                return True
    return False


def tap_text(
    adb: AdbController,
    ocr_results: list[dict],
    patterns: list[str],
    wait: float = 1.0,
    exact: bool = False,
) -> Optional[ActionResult]:
    """Tap by matching text patterns."""
    for pattern in patterns:
        pattern_normalized = normalize_text(pattern)
        for item in ocr_results:
            text = normalize_text(item["text"])
            if exact:
                matched = pattern_normalized == text
            else:
                matched = pattern_normalized in text
            if matched:
                adb.tap_center(item["box"])
                logger.debug(f"点击文字: {pattern}")
                return ActionResult.ok(wait=wait)
    return None


def tap_text_exact(
    adb: AdbController,
    ocr_results: list[dict],
    patterns: list[str],
    wait: float = 1.0,
) -> Optional[ActionResult]:
    return tap_text(
        adb, ocr_results=ocr_results, patterns=patterns, wait=wait, exact=True
    )


def tap_ok(
    adb: AdbController, ocr_results: list[dict], wait: float = 1.0
) -> Optional[ActionResult]:
    """点击 OK 按钮（通用弹窗确认按钮）"""
    return tap_text_exact(adb, ocr_results, get_text_patterns("popup_ok"), wait=wait)


def clear_text(
    adb: AdbController, x: int, y: int, max_chars: int = 20, wait: float = 0.5
) -> ActionResult:
    """
    清空输入框文本

    流程：
    1. 点击输入框获取焦点
    2. 发送多次退格键清空内容

    Args:
        adb: ADB 控制器
        x: 输入框 X 坐标
        y: 输入框 Y 坐标
        max_chars: 最多删除字符数（默认20）
        wait: 操作后等待时间
    """
    device = adb.device
    if device is None:
        logger.error("设备未连接，无法清空输入框")
        return ActionResult.ok(wait=wait)

    # 点击输入框获取焦点
    adb.tap(x, y)
    time.sleep(0.3)

    # 速度优先：使用 uiautomator2 原生清空输入框能力
    device.clear_text()
    time.sleep(0.05)

    logger.debug(f"清空输入框 ({x}, {y})，删除 {max_chars} 个字符")
    return ActionResult.ok(wait=wait)


def tap_by_priority(
    adb: AdbController,
    page_detector,
    ocr_results: Optional[list[dict]] = None,
    patterns: Optional[list[str]] = None,
    template_name: Optional[str] = None,
    wait: float = 1.0,
) -> Optional[ActionResult]:
    """按模板优先、文字次之执行点击"""
    if template_name:
        result = tap_template(adb, page_detector, template_name, wait=wait)
        if result:
            return result

    if not ocr_results or not patterns:
        return None

    result = tap_text(adb, ocr_results, patterns, wait=wait)
    if result:
        return result

    return None


def tap_template_or_text(
    adb: AdbController,
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
    adb: AdbController,
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


def tap_matched_element(
    adb: AdbController, page_info: dict, wait: float = 1.0
) -> Optional[ActionResult]:
    """
    点击匹配到的页面元素（模板或文字）

    优先点击 page_info["matched_template"]
    其次点击 page_info["matched_text"]
    """
    # 1. 尝试点击匹配到的模板
    matched_template = page_info.get("matched_template")
    if matched_template and matched_template.get("box"):
        logger.debug(f"点击匹配模板: {matched_template['template']}")
        return tap_box(adb, matched_template["box"], wait=wait)

    # 2. 尝试点击匹配到的文字
    matched_text = page_info.get("matched_text")
    if matched_text and matched_text.get("box"):
        logger.debug(f"点击匹配文字: {matched_text['matched_text']}")
        return tap_box(adb, matched_text["box"], wait=wait)

    return None


def tap_template_with_scale(
    page_detector,
    template_name: str,
    scale: float,
    threshold: Optional[float] = None,
    wait: float = 1.0,
) -> Optional[ActionResult]:
    """按缩放比例匹配模板并点击"""
    match = page_detector.find_template_with_scale(
        template_name, scale=scale, threshold=threshold
    )
    if not match:
        return None
    return tap_box(page_detector.adb, match.box, wait=wait)


def tap_template_box(
    page_detector,
    template_name: str,
    wait: float = 1.0,
) -> Optional[ActionResult]:
    """查找模板并点击中心（使用 page_detector 最新截图）"""
    box = page_detector.find_template(template_name)
    if not box:
        return None
    return tap_box(page_detector.adb, box, wait=wait)


def tap_above_point(
    adb: AdbController,
    point: Tuple[int, int],
    base_offset_y: int,
    min_y: int = 0,
    wait: float = 1.0,
) -> ActionResult:
    """点击指定点上方（基准像素 + 缩放）"""
    offset_y = adb.scaled_y(base_offset_y)
    tap_x = point[0]
    tap_y = max(point[1] - offset_y, min_y)
    return tap(adb, tap_x, tap_y, wait=wait)


def tap_top_center(adb: AdbController, base_y: int, wait: float = 1.0) -> ActionResult:
    """点击屏幕中上方（基准像素 + 缩放）"""
    tap_x = adb.center_x()
    tap_y = adb.scaled_y(base_y)
    return tap(adb, tap_x, tap_y, wait=wait)


def scroll_until_template(
    page_detector,
    template_name: str,
    scale: float,
    max_attempts: int,
    base_distance_y: int,
    steps: Optional[int] = None,
    wait: float = 1.0,
    threshold: Optional[float] = None,
) -> Optional[ActionResult]:
    """循环上滑直到命中模板或达到上限"""
    screenshot, ocr_results = page_detector.get_last_page_context()
    if not screenshot:
        screenshot, ocr_results = page_detector.capture()
        if not screenshot:
            return None
    last_signature = "|".join(sorted([item["text"] for item in ocr_results]))
    for attempt in range(max_attempts):
        logger.info(f"  -> 第 {attempt + 1} 次上滑查找模板: {template_name}")
        start, end = scroll_points(
            page_detector.adb, base_distance_y=base_distance_y, direction="up"
        )
        swipe(page_detector.adb, start, end, steps=steps, wait=wait)
        time.sleep(wait)
        screenshot, ocr_results = page_detector.capture()
        if not screenshot:
            continue
        match = page_detector.find_template_with_scale(
            template_name, scale=scale, threshold=threshold, screenshot=screenshot
        )
        if match:
            return tap_box(page_detector.adb, match.box, wait=1.0)
        current_signature = "|".join(sorted([item["text"] for item in ocr_results]))
        if current_signature == last_signature:
            logger.warning("  -> 滑动到底部，未找到目标模板")
            break
        last_signature = current_signature
    return None


# 点继续文字
def tap_continue(
    adb: AdbController,
    ocr_results: list[dict],
    patterns: Optional[list[str]] = None,
    wait: float = 1.0,
) -> ActionResult:
    """点击继续文本"""
    if not patterns:
        patterns = get_text_patterns("continue_button")
    result = tap_text(adb, ocr_results, patterns, exact=True, wait=wait)
    if result:
        return result
    return tap_center(adb, wait=wait)


def click_close(
    adb: AdbController, page_detector, ocr_results: list[dict], patterns: list[str]
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


def tap_bottom_close(
    adb: AdbController,
    base_y: int,
    wait: float = 1.0,
    ratio_x: float = 0.1,
) -> ActionResult:
    """点击底部关闭区域（基准像素 + 缩放）"""
    tap_x = int(adb.screen_width * ratio_x)
    tap_y = adb.scaled_y(base_y)
    return tap(adb, tap_x, tap_y, wait=wait)


def tap_home_icon(adb: AdbController, page_detector, wait: float = 1.0) -> ActionResult:
    """点击主页图标"""
    return tap_bottom_icon(adb, page_detector, "icon_home", wait)


def tap_community_icon(adb, page_detector, wait: float = 1.0) -> ActionResult:
    return tap_bottom_icon(adb, page_detector, "icon_community", wait)


def tap_bottom_icon(
    adb: AdbController, page_detector, template_name, wait: float = 1.0
) -> ActionResult:
    result = tap_template(adb, page_detector, template_name=template_name, wait=wait)
    if result:
        return result
    return ActionResult.wait(wait)


def navigate_back(
    adb: AdbController,
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


def swipe_up(
    adb: AdbController,
    base_distance_y: int = BASE_SCROLL_DISTANCE_DEFAULT,
    steps: Optional[int] = SWIPE_STEPS_SCROLL,
    wait: float = 1.0,
) -> ActionResult:
    """向上滑动（基准距离 + 步数）"""
    start, end = scroll_points(adb, base_distance_y, direction="up")
    return swipe(adb, start, end, steps=steps, wait=wait)


def swipe_down(
    adb: AdbController,
    base_distance_y: int = BASE_SCROLL_DISTANCE_DEFAULT,
    steps: Optional[int] = SWIPE_STEPS_SCROLL,
    wait: float = 1.0,
) -> ActionResult:
    """向下滑动（基准距离 + 步数）"""
    start, end = scroll_points(adb, base_distance_y, direction="down")
    return swipe(adb, start, end, steps=steps, wait=wait)


def _clamp_steps(value: float, min_steps: int, max_steps: int) -> int:
    """限制步数范围"""
    return max(min_steps, min(max_steps, int(round(value))))


def calculate_swipe_steps(
    adb: AdbController,
    start: Tuple[int, int],
    end: Tuple[int, int],
    base_ratio: float = SWIPE_STEPS_BASE_RATIO,
    base_steps: int = SWIPE_STEPS_BASE_VALUE,
    min_steps: int = SWIPE_STEPS_MIN,
    max_steps: int = SWIPE_STEPS_MAX,
) -> int:
    """根据距离与屏幕高度计算相对滑动步数"""
    distance_px = math.hypot(end[0] - start[0], end[1] - start[1])
    screen_height = max(1, int(adb.screen_height))
    distance_ratio = distance_px / screen_height
    if base_ratio <= 0:
        return _clamp_steps(base_steps, min_steps, max_steps)
    raw_steps = base_steps * (distance_ratio / base_ratio)
    return _clamp_steps(raw_steps, min_steps, max_steps)


def swipe(
    adb: AdbController,
    start: Tuple[int, int],
    end: Tuple[int, int],
    steps: Optional[int] = None,
    wait: float = 1.0,
) -> ActionResult:
    """执行自定义滑动"""
    resolved_steps = calculate_swipe_steps(adb, start, end) if steps is None else steps
    adb.swipe(*start, *end, resolved_steps)
    return ActionResult.ok(wait=wait)


def perform_swipe(
    adb: AdbController,
    start: Tuple[int, int],
    end: Tuple[int, int],
    steps: Optional[int] = None,
    wait: float = 1.0,
) -> ActionResult:
    """执行滑动动作并返回结果"""
    return swipe(adb, start, end, steps=steps, wait=wait)


def swipe_scaled(
    adb: AdbController,
    start_x: int,
    start_y: int,
    end_x: int,
    end_y: int,
    steps: Optional[int] = None,
    wait: float = 1.0,
) -> ActionResult:
    """基于基准像素执行滑动"""
    return swipe(
        adb,
        (adb.scaled_x(start_x), adb.scaled_y(start_y)),
        (adb.scaled_x(end_x), adb.scaled_y(end_y)),
        steps=steps,
        wait=wait,
    )


def long_press(
    adb: AdbController,
    point: Tuple[int, int],
    steps: int = DEFAULT_LONG_PRESS_STEPS,
    wait: float = 1.0,
) -> ActionResult:
    """长按指定位置（按步数控制时长）"""
    adb.long_press(point[0], point[1], steps)
    return ActionResult.ok(wait=wait)


def long_press_text(
    adb: AdbController,
    ocr_results: list[dict],
    patterns: list[str],
    steps: int = DEFAULT_LONG_PRESS_STEPS,
    wait: float = 1.0,
) -> Optional[ActionResult]:
    """按文本列表匹配长按（按步数控制时长）"""
    for pattern in patterns:
        for item in ocr_results:
            text = "".join(item["text"].lower().split())
            if "".join(pattern.lower().split()) in text:
                box = item["box"]
                cx = (box[0] + box[2]) // 2
                cy = (box[1] + box[3]) // 2
                adb.long_press(cx, cy, steps)
                logger.debug(f"长按文字: {pattern} @ ({cx}, {cy})")
                return ActionResult.ok(wait=wait)
    return None


def pinch_in(
    adb: AdbController,
    center: Tuple[int, int],
    scale: float,
    steps: int,
    wait: float = 0.5,
) -> ActionResult:
    """双指缩小（通用手势封装）"""
    adb.pinch_in(center=center, scale=scale, steps=steps)
    return ActionResult.ok(wait=wait)


def pinch_out(
    adb: AdbController,
    center: Tuple[int, int],
    scale: float,
    steps: int,
    wait: float = 0.5,
) -> ActionResult:
    """双指放大（通用手势封装）"""
    adb.pinch_out(center=center, scale=scale, steps=steps)
    return ActionResult.ok(wait=wait)


def center_point(adb) -> Tuple[int, int]:
    """获取屏幕中心坐标"""
    return adb.center_x(), adb.center_y()


def swipe_pack_coords(adb) -> Tuple[Tuple[int, int], Tuple[int, int]]:
    """获取开包滑动坐标（从左到右）"""
    start_x = adb.scaled_x(BASE_SWIPE_PACK_START_X)
    end_x = adb.scaled_x(BASE_SWIPE_PACK_END_X)
    y = adb.scaled_y(BASE_SWIPE_PACK_END_Y)
    return (start_x, y), (end_x, y)


def swipe_card_coords(adb) -> Tuple[Tuple[int, int], Tuple[int, int]]:
    """获取卡牌上滑坐标（从下到上）"""
    x = adb.center_x()
    start_y = adb.scaled_y(BASE_SWIPE_CARD_START_Y)
    end_y = adb.scaled_y(BASE_SWIPE_CARD_END_Y)
    return (x, start_y), (x, end_y)


def scroll_points(
    adb: AdbController,
    base_distance_y: int,
    direction: str = "up",
) -> Tuple[Tuple[int, int], Tuple[int, int]]:
    """根据基准距离生成垂直滑动起止点"""
    distance = adb.scaled_y(base_distance_y)
    cx = adb.center_x()
    cy = adb.center_y()
    start_y = cy + distance // 2
    end_y = cy - distance // 2
    if direction == "down":
        return (cx, end_y), (cx, start_y)
    return (cx, start_y), (cx, end_y)


def input_text(adb: AdbController, text: str, wait: float = 0.5) -> ActionResult:
    """输入文本（直接调用设备输入能力）"""
    device = adb.device
    if device is None:
        logger.error("设备未连接，无法输入文本")
        return ActionResult.ok(wait=wait)

    try:
        device.send_keys(text)
        return ActionResult.ok(wait=wait)
    except Exception as exc:
        logger.error(f"输入文本失败: {exc}")
        return ActionResult.ok(wait=wait)
