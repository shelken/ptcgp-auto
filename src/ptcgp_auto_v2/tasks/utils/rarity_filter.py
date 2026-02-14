# -*- coding: utf-8 -*-
"""筛选面板稀有度点击工具。"""

from __future__ import annotations

from typing import Optional

from ptcgp_auto_v2.config.rarity_icons import (
    RARITY_CODE_REVERSE,
    RARITY_GROUP_DEFAULTS,
    RARITY_ICON_TEMPLATES,
)
from ptcgp_auto_v2.core.task_base import ActionResult
from ptcgp_auto_v2.infra.icon_group_detector import find_group_by_rarity
from ptcgp_auto_v2.utils.gesture import tap


def select_rarity_in_filter_panel(
    adb,
    page_detector,
    icon_detector,
    rarity_code: str,
    wait: float = 0.4,
) -> Optional[ActionResult]:
    """匹配目标稀有度，点击，结束。"""
    screenshot, _ = page_detector.get_last_page_context()
    if screenshot is None:
        screenshot, _ = page_detector.capture()
        if screenshot is None:
            return None

    hits = icon_detector.detect_icons(
        screenshot=screenshot,
        template_paths=RARITY_ICON_TEMPLATES,
        roi=None,  # 在当前页面全屏范围匹配稀有度图标
        threshold=RARITY_GROUP_DEFAULTS["threshold"],  # 图标匹配置信度阈值
        nms_iou=RARITY_GROUP_DEFAULTS["nms_iou"],  # NMS 去重 IoU 阈值
        screen_width=adb.screen_width,
    )
    groups = icon_detector.group_hits(
        hits,
        row_tol=adb.scaled_y(RARITY_GROUP_DEFAULTS["row_tol_px"]),  # 分组行容差
        gap=adb.scaled_x(RARITY_GROUP_DEFAULTS["gap_px"]),  # 同行图标间隔容差
        min_count=RARITY_GROUP_DEFAULTS["min_count"],  # 形成有效分组最少图标数
    )

    group = find_group_by_rarity(rarity_code, groups, RARITY_CODE_REVERSE)
    if group is None:
        return None
    return tap(adb, int(group.center[0]), int(group.center[1]), wait=wait)
