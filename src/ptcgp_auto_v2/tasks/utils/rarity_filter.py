# -*- coding: utf-8 -*-
"""筛选面板稀有度选择工具。

提供完整的筛选面板处理流程：
1. 点击"清除"
2. 上滑显示更多稀有度选项
3. 选择目标稀有度
4. 下滑找到 OK 按钮（如需要）
5. 点击 OK
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Optional

from ptcgp_auto_v2.config.constants import SWIPE_STEPS_SCROLL
from ptcgp_auto_v2.config.rarity_icons import (
    RARITY_CODE_REVERSE,
    RARITY_GROUP_DEFAULTS,
    RARITY_ICON_TEMPLATES,
)
from ptcgp_auto_v2.core.task_base import ActionResult
from ptcgp_auto_v2.infra.icon_group_detector import find_group_by_rarity
from ptcgp_auto_v2.locales import get_text_patterns
from ptcgp_auto_v2.utils.gesture import (
    scroll_points,
    swipe,
    tap,
    tap_ok,
    tap_text_exact,
)

if TYPE_CHECKING:
    from ptcgp_auto_v2.infra.adb import AdbController
    from ptcgp_auto_v2.infra.icon_group_detector import IconGroupDetector
    from ptcgp_auto_v2.infra.page_detector import PageDetector

logger = logging.getLogger(__name__)

BASE_FILTER_SCROLL_DISTANCE_Y = 192
BASE_FILTER_OK_SCROLL_DISTANCE_Y = 154
FILTER_SCROLL_WAIT = 1.2


@dataclass
class FilterPanelState:
    """筛选面板状态。"""

    cleared: bool = False
    scrolled: bool = False
    ok_scrolled: bool = False


@dataclass
class FilterPanelHandler:
    """筛选面板处理器，封装完整筛选流程。"""

    adb: "AdbController"
    page_detector: "PageDetector"
    icon_detector: "IconGroupDetector"
    state: FilterPanelState = field(default_factory=FilterPanelState)
    action_cache: dict[str, bool] = field(default_factory=dict)

    def reset(self):
        """重置状态。"""
        self.state = FilterPanelState()
        self.action_cache.clear()

    def _is_done(self, key: str) -> bool:
        return self.action_cache.get(key, False)

    def _mark_done(self, key: str):
        self.action_cache[key] = True

    def handle(self, page_info: dict, rarity_codes: list[str]) -> ActionResult:
        """
        处理筛选面板，执行完整筛选流程。

        Args:
            page_info: 页面信息，包含 ocr_results
            rarity_codes: 目标稀有度列表，如 ["SR", "AR", "SAR"]

        Returns:
            ActionResult
        """
        ocr_results = page_info.get("ocr_results", [])

        no_target_box = self._find_text_box(
            ocr_results, get_text_patterns("card_filter_no_target"), exact=False
        )
        if no_target_box:
            logger.info("筛选界面提示无对象卡牌")
            return ActionResult.ok(wait=0.5)

        if not self._is_done("filter_cleared"):
            result = tap_text_exact(
                self.adb,
                ocr_results,
                get_text_patterns("card_filter_clear"),
                wait=0.5,
            )
            if result:
                self._mark_done("filter_cleared")
                return result
            return ActionResult.ok(wait=0.5)

        if not self._is_done("filter_scrolled"):
            start, end = scroll_points(
                self.adb, base_distance_y=BASE_FILTER_SCROLL_DISTANCE_Y, direction="up"
            )
            swipe(
                self.adb,
                start,
                end,
                steps=SWIPE_STEPS_SCROLL,
                wait=FILTER_SCROLL_WAIT,
            )
            self._mark_done("filter_scrolled")
            return ActionResult.ok(wait=FILTER_SCROLL_WAIT)

        if not self._is_done("filter_selected"):
            result = self._select_rarities(rarity_codes)
            if result:
                self._mark_done("filter_selected")
                ok_result = tap_ok(self.adb, ocr_results, wait=1.0)
                if ok_result:
                    self._mark_done("filter_applied")
                    return ok_result
                if not self._is_done("filter_ok_scrolled"):
                    start, end = scroll_points(
                        self.adb,
                        base_distance_y=BASE_FILTER_OK_SCROLL_DISTANCE_Y,
                        direction="down",
                    )
                    swipe(
                        self.adb,
                        start,
                        end,
                        steps=SWIPE_STEPS_SCROLL,
                        wait=0.8,
                    )
                    self._mark_done("filter_ok_scrolled")
                    return ActionResult.ok(wait=0.8)
                return result
            return ActionResult.ok(wait=0.5)

        result = tap_ok(self.adb, ocr_results, wait=1.0)
        if result:
            self._mark_done("filter_applied")
        return result or ActionResult.ok(wait=0.5)

    def _select_rarities(self, rarity_codes: list[str]) -> Optional[ActionResult]:
        """按稀有度列表选择筛选项。"""
        screenshot, _ = self.page_detector.get_last_page_context()
        if screenshot is None:
            screenshot, _ = self.page_detector.capture()
            if screenshot is None:
                return None

        hits = self.icon_detector.detect_icons(
            screenshot=screenshot,
            template_paths=RARITY_ICON_TEMPLATES,
            roi=None,
            threshold=RARITY_GROUP_DEFAULTS["threshold"],
            nms_iou=RARITY_GROUP_DEFAULTS["nms_iou"],
            screen_width=self.adb.screen_width,
        )
        groups = self.icon_detector.group_hits(
            hits,
            row_tol=self.adb.scaled_y(RARITY_GROUP_DEFAULTS["row_tol_px"]),
            gap=self.adb.scaled_x(RARITY_GROUP_DEFAULTS["gap_px"]),
            min_count=RARITY_GROUP_DEFAULTS["min_count"],
        )

        clicked = False
        visited = set()
        for rarity_code in rarity_codes:
            pattern = RARITY_CODE_REVERSE.get(rarity_code)
            if not pattern:
                continue
            if pattern in visited:
                continue
            visited.add(pattern)
            group = find_group_by_rarity(rarity_code, groups, RARITY_CODE_REVERSE)
            if group is None:
                logger.debug("未找到稀有度分组: %s", rarity_code)
                continue
            tap(self.adb, int(group.center[0]), int(group.center[1]), wait=0.2)
            logger.info("已选择稀有度: %s", rarity_code)
            clicked = True

        return ActionResult.ok(wait=0.5) if clicked else None

    @staticmethod
    def _find_text_box(
        ocr_results: list[dict], patterns: list[str], exact: bool = False
    ) -> Optional[tuple[int, int, int, int]]:
        for pattern in patterns:
            pattern_norm = "".join(pattern.lower().split())
            for item in ocr_results:
                text = "".join(item.get("text", "").lower().split())
                if exact:
                    matched = pattern_norm == text
                else:
                    matched = pattern_norm in text
                if matched:
                    box = item.get("box")
                    if box and len(box) == 4:
                        return tuple(box)
        return None


def handle_filter_panel(
    adb: "AdbController",
    page_detector: "PageDetector",
    icon_detector: "IconGroupDetector",
    page_info: dict,
    rarity_codes: list[str],
    state: Optional[FilterPanelState] = None,
    action_cache: Optional[dict[str, bool]] = None,
) -> ActionResult:
    """
    处理筛选面板的便捷函数。

    Args:
        adb: ADB 控制器
        page_detector: 页面检测器
        icon_detector: 图标检测器
        page_info: 页面信息
        rarity_codes: 目标稀有度列表
        state: 筛选状态（可选，用于跨轮次保持状态）
        action_cache: 动作缓存（可选）

    Returns:
        ActionResult
    """
    handler = FilterPanelHandler(
        adb=adb,
        page_detector=page_detector,
        icon_detector=icon_detector,
        state=state if state is not None else FilterPanelState(),
        action_cache=action_cache if action_cache is not None else {},
    )
    return handler.handle(page_info, rarity_codes)
