# -*- coding: utf-8 -*-
"""
好友列表与卡牌扫��流程辅助函数。

供 send_card_daily 和 exchange_cards 共用。
"""

from typing import TYPE_CHECKING, Optional

from ptcgp_auto_v2.core.task_base import ActionResult
from ptcgp_auto_v2.tasks.utils.constants import (
    BASE_FRIEND_ROW_THRESHOLD_Y,
    BASE_FRIEND_SCROLL_DISTANCE_Y,
)
from ptcgp_auto_v2.utils.gesture import scroll_points, swipe

if TYPE_CHECKING:
    from ptcgp_auto_v2.infra.page_detector import PageDetector


AMBIGUOUS_NICKNAME_CHARS = {"0", "o", "i", "l"}


def _normalize_text(text: str) -> str:
    """基础归一化：小写并移除空白。"""
    return "".join(text.lower().split())


def _normalize_nickname_for_match(text: str) -> str:
    """昵称匹配归一化：过滤易混淆字符后再比较。"""
    normalized = _normalize_text(text)
    stripped = "".join(
        char for char in normalized if char not in AMBIGUOUS_NICKNAME_CHARS
    )
    return stripped or normalized


def build_ocr_signature(ocr_results: list[dict]) -> str:
    """构建 OCR 文本签名。"""
    texts = [str(item.get("text", "")).strip() for item in ocr_results]
    return "|".join(sorted(texts))


def build_detect_signature(detected) -> str:
    """构建识别结果签名，用于判断列表是否变化。"""
    if not detected:
        return "__EMPTY__"
    items: list[str] = []
    for item in detected:
        if not item.set_code:
            continue
        items.append(f"{item.set_code}:{item.card_number}")
    if not items:
        return "__EMPTY__"
    return "|".join(sorted(items))


def find_target_search_plus_box(
    ocr_results: list[dict],
    target_nickname: str,
    search_plus_boxes: list[tuple[int, int, int, int]],
    row_threshold_y: int,
) -> Optional[tuple[int, int, int, int]]:
    """按昵称找到同一行最接近的 icon_search_plus。"""
    if not target_nickname or not search_plus_boxes:
        return None

    target_text = _normalize_nickname_for_match(target_nickname)
    nickname_boxes: list[tuple[int, int, int, int]] = []
    for item in ocr_results:
        text = _normalize_nickname_for_match(str(item.get("text", "")))
        if text != target_text:
            continue
        box = item.get("box")
        if box and len(box) == 4:
            nickname_boxes.append(tuple(box))

    if not nickname_boxes:
        return None

    best: Optional[tuple[int, int, int, int]] = None
    best_distance: Optional[int] = None
    for nickname_box in nickname_boxes:
        nickname_cy = (nickname_box[1] + nickname_box[3]) // 2
        for plus_box in search_plus_boxes:
            plus_cy = (plus_box[1] + plus_box[3]) // 2
            distance = abs(plus_cy - nickname_cy)
            if distance > row_threshold_y:
                continue
            if best_distance is None or distance < best_distance:
                best_distance = distance
                best = plus_box
    return best


def find_send_box_near_anchor(
    ocr_results: list[dict],
    send_text_patterns: list[str],
    anchor_y: int,
    row_threshold_y: int,
) -> Optional[tuple[int, int, int, int]]:
    """按锚点 Y 轴在同一行查找分送按钮。"""
    send_patterns = {_normalize_text(t) for t in send_text_patterns}
    candidates: list[tuple[int, tuple[int, int, int, int]]] = []
    for item in ocr_results:
        text = _normalize_text(str(item.get("text", "")))
        if text not in send_patterns:
            continue
        box = item.get("box")
        if not box or len(box) != 4:
            continue
        cy = (box[1] + box[3]) // 2
        if abs(cy - anchor_y) > row_threshold_y:
            continue
        candidates.append((abs(cy - anchor_y), tuple(box)))

    if not candidates:
        return None
    candidates.sort(key=lambda item: item[0])
    return candidates[0][1]


def scroll_friend_list(
    adb,
    direction: str = "up",
    base_distance_y: int = BASE_FRIEND_SCROLL_DISTANCE_Y,
    wait_scroll: float = 0.9,
    wait_after: float = 0.8,
) -> ActionResult:
    """通用好友列表滑动。"""
    start, end = scroll_points(
        adb, base_distance_y=base_distance_y, direction=direction
    )
    swipe(adb, start, end, wait=wait_scroll)
    return ActionResult.ok(wait=wait_after)


def find_all_search_plus_boxes(
    page_detector: "PageDetector",
    template_name: str = "icon_search_plus",
    threshold: float = 0.8,
) -> list[tuple[int, int, int, int]]:
    """查找页面上所有搜索加号图标，按 Y 轴从上到下排序。"""
    if not hasattr(page_detector, "find_all_templates"):
        return []
    matches = page_detector.find_all_templates(
        template_name, threshold=threshold, scale=1.0
    )
    boxes: list[tuple[int, int, int, int]] = []
    for match in matches:
        box = getattr(match, "box", None)
        if box and len(box) == 4:
            boxes.append(tuple(box))
    boxes.sort(key=lambda b: (b[1] + b[3]) // 2)
    return boxes
