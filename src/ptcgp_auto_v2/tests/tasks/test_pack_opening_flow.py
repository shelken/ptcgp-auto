# -*- coding: utf-8 -*-
import sys
import unittest
from pathlib import Path

src_dir = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(src_dir))

from ptcgp_auto_v2.tasks.utils.pack_opening_flow import (  # noqa: E402
    long_press_opening_card,
    swipe_card_register,
    swipe_open_pack,
    tap_opening_continue,
)
from ptcgp_auto_v2.tests.fake_adb import FakeAdb  # noqa: E402


class TestPackOpeningFlow(unittest.TestCase):
    """测试开包通用流程工具函数。"""

    def test_swipe_open_pack_executes_horizontal_swipe(self):
        adb = FakeAdb()

        result = swipe_open_pack(adb)

        self.assertTrue(result.success)
        self.assertEqual(1, len(adb.swipes))
        start, end, _ = adb.swipes[0]
        self.assertGreater(end[0], start[0])
        self.assertEqual(start[1], end[1])

    def test_swipe_card_register_executes_vertical_swipe(self):
        adb = FakeAdb()

        result = swipe_card_register(adb)

        self.assertTrue(result.success)
        self.assertEqual(1, len(adb.swipes))
        start, end, _ = adb.swipes[0]
        self.assertEqual(start[0], end[0])
        self.assertGreater(start[1], end[1])

    def test_long_press_opening_card_long_presses_when_text_found(self):
        adb = FakeAdb()
        ocr_results = [
            {"text": "長按", "box": (100, 200, 220, 280)},
        ]

        result = long_press_opening_card(adb, ocr_results)

        self.assertIsNotNone(result)
        self.assertEqual(1, len(adb.long_presses))

    def test_tap_opening_continue_fallbacks_to_center_tap(self):
        adb = FakeAdb()

        result = tap_opening_continue(adb, ocr_results=[])

        self.assertTrue(result.success)
        self.assertEqual(1, len(adb.tap_points))
        self.assertEqual((adb.center_x(), adb.center_y()), adb.tap_points[0])


if __name__ == "__main__":
    unittest.main()
