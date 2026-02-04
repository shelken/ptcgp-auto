# -*- coding: utf-8 -*-
"""
得卡/初始化选卡辅助方法测试
"""

import sys
import unittest
from pathlib import Path

src_dir = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(src_dir))

from ptcgp_auto_v2.core.task_base import ActionResult
from ptcgp_auto_v2.tasks.utils.card_pick import tap_favorite_card


class FakeAdb:
    """模拟 ADB 控制器"""

    def __init__(self):
        self.taps = []
        self._screen_width = 1080
        self._screen_height = 1920

    @property
    def screen_width(self):
        return self._screen_width

    @property
    def screen_height(self):
        return self._screen_height

    def tap(self, x, y):
        self.taps.append((x, y))

    def scaled_y(self, y):
        return int(y * self._screen_height / 1920)

    def center_x(self):
        return self._screen_width // 2


class TestCardPickHelper(unittest.TestCase):
    """测试选卡辅助方法"""

    def test_tap_favorite_card_uses_base_y(self):
        """测试使用基准像素点击卡牌"""
        adb = FakeAdb()

        result = tap_favorite_card(adb)

        self.assertIsInstance(result, ActionResult)
        self.assertEqual(len(adb.taps), 1)
        self.assertEqual(adb.taps[0][0], adb.center_x())
        self.assertEqual(adb.taps[0][1], adb.scaled_y(740))


if __name__ == "__main__":
    unittest.main()
