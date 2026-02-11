import sys
import unittest
from pathlib import Path
from types import SimpleNamespace

src_dir = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(src_dir))

from ptcgp_auto_v2.tasks.claim_gifts import ClaimGiftsTask
from ptcgp_auto_v2.tests.fake_adb import FakeAdb


class FakePageDetector:
    def __init__(self, gift_match=None, screenshot=None):
        self._gift_match = gift_match
        self._last_screenshot = screenshot if screenshot is not None else object()
        self._last_ocr_results = []

    def capture(self, screenshot=None):
        return self._last_screenshot, self._last_ocr_results

    def find_template_with_scale(
        self, template_name, scale=1.0, threshold=None, screenshot=None
    ):
        if template_name == "icon_gift":
            return self._gift_match
        return None


class TestClaimGiftsHandleHome(unittest.TestCase):
    def test_handle_home_no_gift_sets_no_gifts_phase(self):
        adb = FakeAdb()
        page_detector = FakePageDetector(gift_match=None)
        task = ClaimGiftsTask(adb, recognizer=None, page_detector=page_detector)

        result = task._handle_home({})

        self.assertTrue(result.success)
        self.assertTrue(task._completed)
        self.assertEqual([], adb.taps)

    def test_handle_home_gift_icon_taps_and_enters(self):
        adb = FakeAdb()
        gift_match = SimpleNamespace(box=(10, 20, 30, 40))
        page_detector = FakePageDetector(gift_match=gift_match)
        task = ClaimGiftsTask(adb, recognizer=None, page_detector=page_detector)

        result = task._handle_home({})

        self.assertTrue(result.success)
        self.assertFalse(task._completed)
        self.assertEqual([gift_match.box], adb.taps)


class TestClaimGiftsCardRegister(unittest.TestCase):
    """测试礼物领取后的图鉴登录页处理。"""

    def test_handle_card_register_swipes_up(self):
        adb = FakeAdb()
        page_detector = FakePageDetector(gift_match=None)
        task = ClaimGiftsTask(adb, recognizer=None, page_detector=page_detector)

        result = task._handle_card_register({"ocr_results": []})

        self.assertTrue(result.success)
        self.assertEqual(1, len(adb.swipes))
        start, end, _ = adb.swipes[0]
        self.assertEqual(start[0], end[0])
        self.assertGreater(start[1], end[1])


if __name__ == "__main__":
    unittest.main()
