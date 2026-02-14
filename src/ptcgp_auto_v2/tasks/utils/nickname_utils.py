# -*- coding: utf-8 -*-
"""昵称提取工具。"""

from __future__ import annotations

from typing import Optional


def extract_nickname_near_friend_id(
    ocr_results: list[dict],
    target_friend_id: str,
    excluded_patterns: set[str],
    row_threshold_y: int = 140,
) -> Optional[str]:
    """在包含目标 friend_id 的同一行提取昵称。"""
    normalized_target = "".join(ch for ch in (target_friend_id or "") if ch.isdigit())
    if not normalized_target:
        return None

    anchor_box = None
    for item in ocr_results:
        text = str(item.get("text", ""))
        digits = "".join(ch for ch in text if ch.isdigit())
        if digits != normalized_target:
            continue
        box = item.get("box")
        if box and len(box) == 4:
            anchor_box = tuple(box)
            break

    if not anchor_box:
        return None

    anchor_cy = (anchor_box[1] + anchor_box[3]) // 2
    anchor_x1 = anchor_box[0]
    candidates: list[tuple[int, str]] = []
    for item in ocr_results:
        text = str(item.get("text", "")).strip()
        compact = "".join(text.lower().split())
        if not text or compact in excluded_patterns:
            continue
        box = item.get("box")
        if not box or len(box) != 4:
            continue
        cy = (box[1] + box[3]) // 2
        cx = (box[0] + box[2]) // 2
        if cx >= anchor_x1:
            continue
        distance = abs(cy - anchor_cy)
        if distance > row_threshold_y:
            continue
        if len(text) < 2:
            continue
        if text.replace(",", "").replace(".", "").isdigit():
            continue
        candidates.append((distance, text))

    if not candidates:
        return None
    candidates.sort(key=lambda item: item[0])
    return candidates[0][1]


def extract_nickname_by_lv(
    ocr_results: list[dict],
    search_range_y: int,
    excluded_contains: list[str],
) -> Optional[str]:
    """按 fetch_account_info 逻辑从 Lv 下方提取昵称。"""
    lv_y = None
    for item in ocr_results:
        text = str(item.get("text", ""))
        if text.startswith("Lv"):
            box = item.get("box")
            if box and len(box) == 4:
                lv_y = (box[1] + box[3]) // 2
                break
    if lv_y is None:
        return None

    candidates: list[tuple[str, int]] = []
    for item in ocr_results:
        text = str(item.get("text", ""))
        box = item.get("box")
        if not box or len(box) != 4:
            continue
        y = (box[1] + box[3]) // 2
        if not (lv_y < y < lv_y + search_range_y):
            continue
        if any(p in text for p in excluded_contains):
            continue
        if (
            "/" in text
            and text.replace(",", "").replace("/", "").replace(".", "").isdigit()
        ):
            continue
        if text.replace(",", "").replace(".", "").isdigit():
            continue
        if len(text.strip()) >= 2:
            candidates.append((text.strip(), y))

    if not candidates:
        return None
    candidates.sort(key=lambda item: item[1])
    return candidates[0][0]
