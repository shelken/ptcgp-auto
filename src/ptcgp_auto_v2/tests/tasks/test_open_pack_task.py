import sys
import unittest
from pathlib import Path
from types import SimpleNamespace

src_dir = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(src_dir))

from ptcgp_auto_v2.tasks.open_pack import OpenPackPhase, OpenPackTask
from ptcgp_auto_v2.utils.gesture import scroll_until_template
from ptcgp_auto_v2.config.constants import DEFAULT_TEMPLATE_THRESHOLD


class FakeAdb:
    def __init__(self):
        self.taps = []
        self.tap_points = []
        self.screen_width = 1080
        self.screen_height = 1920

    def tap_center(self, box):
        self.taps.append(box)

    def tap(self, x, y):
        self.tap_points.append((x, y))

    def swipe_up(self, ratio=0.26):
        return None


class FakePageDetector:
    def __init__(
        self,
        free_match=None,
        pack_match=None,
        screenshot=None,
        capture_sequence=None,
        template_sequence=None,
    ):
        self._free_match = free_match
        self._pack_match = pack_match
        self._last_screenshot = screenshot if screenshot is not None else object()
        self._last_ocr_results = []
        self._capture_sequence = capture_sequence or []
        self._capture_index = 0
        self._template_sequence = template_sequence or []
        self._template_index = 0
        self.adb = FakeAdb()

    def get_last_page_context(self):
        return self._last_screenshot, self._last_ocr_results

    def capture(self, screenshot=None):
        if self._capture_index < len(self._capture_sequence):
            item = self._capture_sequence[self._capture_index]
            self._capture_index += 1
            self._last_screenshot = item[0]
            self._last_ocr_results = item[1]
            return item
        self._last_screenshot = None
        self._last_ocr_results = []
        return None, []

    def find_template_with_scale(
        self, template_name, scale=1.0, threshold=DEFAULT_TEMPLATE_THRESHOLD, screenshot=None
    ):
        if template_name == "icon_free_pack_available":
            return self._free_match
        if template_name == "icon_pack_open":
            return self._pack_match
        if self._template_index < len(self._template_sequence):
            match = self._template_sequence[self._template_index]
            self._template_index += 1
            return match
        return None


class TestOpenPackHandleHome(unittest.TestCase):
    def test_handle_home_no_free_pack_sets_no_free_pack_phase(self):
        adb = FakeAdb()
        page_detector = FakePageDetector()
        task = OpenPackTask(adb, recognizer=None, page_detector=page_detector)
        task._phase = OpenPackPhase.CHECKING_HOME

        for _ in range(task.HOME_CHECK_THRESHOLD):
            result = task._handle_home({})
            self.assertTrue(result.success)

        self.assertEqual(OpenPackPhase.NO_FREE_PACK, task._phase)
        self.assertEqual([], adb.taps)

    def test_handle_home_free_pack_prefers_pack_open_icon(self):
        adb = FakeAdb()
        free_match = SimpleNamespace(box=(10, 20, 30, 40))
        pack_match = SimpleNamespace(box=(50, 60, 70, 80))
        page_detector = FakePageDetector(free_match=free_match, pack_match=pack_match)
        task = OpenPackTask(adb, recognizer=None, page_detector=page_detector)
        task._phase = OpenPackPhase.CHECKING_HOME
        task._home_check_count = 2

        result = task._handle_home({})

        self.assertTrue(result.success)
        self.assertEqual(OpenPackPhase.ENTERING_PACK, task._phase)
        self.assertEqual(0, task._home_check_count)
        self.assertEqual([pack_match.box], adb.taps)

    def test_handle_home_free_pack_skips_free_pack_icon_when_no_open_icon(self):
        adb = FakeAdb()
        free_match = SimpleNamespace(box=(1, 2, 3, 4))
        page_detector = FakePageDetector(free_match=free_match, pack_match=None)
        task = OpenPackTask(adb, recognizer=None, page_detector=page_detector)
        task._phase = OpenPackPhase.CHECKING_HOME
        task._home_check_count = 1

        result = task._handle_home({})

        self.assertTrue(result.success)
        self.assertEqual(OpenPackPhase.ENTERING_PACK, task._phase)
        self.assertEqual(0, task._home_check_count)
        self.assertEqual([], adb.taps)


class TestGestureTemplateFlows(unittest.TestCase):
    def test_scroll_until_template_hits_match(self):
        match = SimpleNamespace(box=(1, 2, 3, 4))
        capture_sequence = [
            (object(), [{"text": "alpha"}]),
            (object(), [{"text": "beta"}]),
        ]
        page_detector = FakePageDetector(
            capture_sequence=capture_sequence,
            template_sequence=[None, match],
        )
        result = scroll_until_template(
            page_detector,
            template_name="target",
            scale=1.0,
            max_attempts=3,
            swipe_ratio=0.2,
            wait=0.1,
        )

        self.assertIsNotNone(result)
        self.assertEqual([match.box], page_detector.adb.taps)

    def test_scroll_until_template_stops_on_repeat_signature(self):
        capture_sequence = [
            (object(), [{"text": "same"}]),
            (object(), [{"text": "same"}]),
        ]
        page_detector = FakePageDetector(
            capture_sequence=capture_sequence,
            template_sequence=[None, None],
        )
        result = scroll_until_template(
            page_detector,
            template_name="target",
            scale=1.0,
            max_attempts=3,
            swipe_ratio=0.2,
            wait=0.1,
        )

        self.assertIsNone(result)
        self.assertEqual([], page_detector.adb.taps)

if __name__ == "__main__":
    unittest.main()
