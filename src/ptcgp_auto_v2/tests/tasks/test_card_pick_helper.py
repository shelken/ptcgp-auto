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
from ptcgp_auto_v2.tests.fake_adb import FakeAdb


class TestCardPickHelper(unittest.TestCase):
    """测试选卡辅助方法"""

    def test_tap_favorite_card_uses_base_y(self):
        """测试使用基准像素点击卡牌"""
        adb = FakeAdb()

        result = tap_favorite_card(adb)

        self.assertIsInstance(result, ActionResult)
        self.assertEqual(len(adb.tap_points), 1)
        self.assertEqual(adb.tap_points[0][0], adb.center_x())
        self.assertEqual(adb.tap_points[0][1], adb.scaled_y(740))


if __name__ == "__main__":
    unittest.main()
