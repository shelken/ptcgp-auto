# -*- coding: utf-8 -*-
"""昵称提取工具。"""

from __future__ import annotations

from typing import Optional


def extract_nickname_by_lv(
    ocr_results: list[dict],
    search_range_y: int,
    excluded_contains: list[str],
) -> Optional[str]:
    """从 Lv 下方提取昵称（用于详情页面）。

    好友详情页布局：Lv 在上方，昵称在 Lv 下方。
    """
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
