# -*- coding: utf-8 -*-
"""
手势工具最小单测
"""

from ptcgp_auto_v2.utils.gesture import (
    is_text_visible,
    normalize_text,
    scroll_points,
)


class DummyAdb:
    """测试用 ADB 适配器。"""

    def __init__(self, screen_width: int, screen_height: int):
        """初始化屏幕尺寸。"""
        self.screen_width = screen_width
        self.screen_height = screen_height

    def scaled_y(self, y: int) -> int:
        """按原值返回，便于断言。"""
        return y

    def center_x(self) -> int:
        """返回屏幕中心 X 坐标。"""
        return self.screen_width // 2

    def center_y(self) -> int:
        """返回屏幕中心 Y 坐标。"""
        return self.screen_height // 2


def test_normalize_text_and_match():
    """验证文本规范化与匹配逻辑。"""
    assert normalize_text("  Te st ") == "test"
    assert is_text_visible([{"text": "OK", "box": (0, 0, 10, 10)}], ["ok"], exact=True)


def test_scroll_points_up_and_down():
    """验证上滑与下滑的起止点方向。"""
    adb = DummyAdb(screen_width=1080, screen_height=1920)
    start_up, end_up = scroll_points(adb, base_distance_y=500, direction="up")
    start_down, end_down = scroll_points(adb, base_distance_y=500, direction="down")
    assert start_up[1] > end_up[1]
    assert start_down[1] < end_down[1]
