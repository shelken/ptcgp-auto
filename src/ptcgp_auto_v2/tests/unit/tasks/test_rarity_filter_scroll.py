# -*- coding: utf-8 -*-
"""筛选稀有度区域定位回归测试。"""

from ptcgp_auto_v2.tasks.utils.rarity_filter import FilterPanelHandler


class _Adb:
    screen_width = 720
    screen_height = 1280

    def __init__(self):
        self.swipes: list[tuple[int, int, int, int, int]] = []

    def center_x(self):
        return self.screen_width // 2

    def center_y(self):
        return self.screen_height // 2

    def scaled_x(self, value: int):
        return int(value * self.screen_width / 1080)

    def scaled_y(self, value: int):
        return int(value * self.screen_height / 1920)

    def swipe(self, x1: int, y1: int, x2: int, y2: int, steps: int):
        self.swipes.append((x1, y1, x2, y2, steps))


def _handler(action_cache: dict[str, bool], adb: _Adb | None = None):
    return FilterPanelHandler(
        adb=adb or _Adb(),
        page_detector=object(),
        icon_detector=object(),
        action_cache=action_cache,
    )


def _ocr(text: str, box: tuple[int, int, int, int]) -> dict:
    return {"text": text, "box": box}


def test_scroll_does_not_finish_when_rarity_title_below_screen_center():
    """稀有度标题仍在屏幕中线下方时，继续滑动且不能进入选择阶段。"""
    action_cache = {"filter_cleared": True}
    adb = _Adb()
    handler = _handler(action_cache, adb=adb)

    handler.handle({"ocr_results": [_ocr("稀有度", (60, 700, 120, 736))]}, ["SR"])

    assert len(adb.swipes) == 1
    assert action_cache.get("filter_scrolled") is not True


def test_scroll_finishes_only_when_rarity_title_above_screen_center():
    """稀有度标题已在屏幕中线上方时，停止滑动并允许后续选择稀有度。"""
    action_cache = {"filter_cleared": True}
    adb = _Adb()
    handler = _handler(action_cache, adb=adb)

    handler.handle({"ocr_results": [_ocr("稀有度", (60, 480, 120, 520))]}, ["SR"])

    assert adb.swipes == []
    assert action_cache["filter_scrolled"] is True
