import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from typing import cast
from unittest.mock import patch

src_dir = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(src_dir))

from ptcgp_auto_v2.core.task_base import ActionResult
from ptcgp_auto_v2.infra.adb import AdbController
from ptcgp_auto_v2.infra.page_detector import PageDetector
from ptcgp_auto_v2.tasks.fetch_account_info import FetchAccountInfoTask


class TestFetchAccountInfoTask(unittest.TestCase):
    @staticmethod
    def _build_adb_stub():
        return cast(
            AdbController,
            SimpleNamespace(
                scaled_x=lambda x: x,
                scaled_y=lambda y: y,
                center_x=lambda: 540,
            ),
        )

    def test_extract_holdings_values_from_holdings_page(self):
        adb = self._build_adb_stub()
        page_detector = cast(PageDetector, object())
        task = FetchAccountInfoTask(
            adb=adb, recognizer=None, page_detector=page_detector
        )

        ocr = [
            {"text": "閃亮沙子", "box": (250, 560, 420, 620)},
            {"text": "3,700", "box": (900, 630, 980, 680)},
            {"text": "開包沙漏", "box": (360, 1620, 470, 1680)},
            {"text": "220", "box": (180, 1710, 260, 1760)},
        ]

        exchange_points, pack_hourglass_count = task._extract_holdings_values(ocr)  # type: ignore[attr-defined]

        self.assertEqual(3700, exchange_points)
        self.assertEqual(220, pack_hourglass_count)

    @patch("ptcgp_auto_v2.tasks.fetch_account_info.tap_template")
    def test_handle_home_should_tap_more_when_profile_done(self, tap_template_mock):
        adb = self._build_adb_stub()
        page_detector = cast(PageDetector, object())
        task = FetchAccountInfoTask(
            adb=adb, recognizer=None, page_detector=page_detector
        )
        task._mark_action_done("profile_fetched")  # type: ignore[attr-defined]
        tap_template_mock.return_value = ActionResult.ok(wait=0.1)

        result = task._handle_home({"ocr_results": []})  # type: ignore[attr-defined]

        self.assertTrue(result.success)
        self.assertTrue(task._is_action_done("more_menu_opened"))  # type: ignore[attr-defined]
        tap_template_mock.assert_called_once()

    @patch("ptcgp_auto_v2.tasks.fetch_account_info.tap_text")
    def test_handle_more_menu_modal_should_click_holdings_exact(self, tap_text_mock):
        adb = self._build_adb_stub()
        page_detector = cast(PageDetector, object())
        task = FetchAccountInfoTask(
            adb=adb, recognizer=None, page_detector=page_detector
        )
        tap_text_mock.return_value = ActionResult.ok(wait=0.1)

        result = task._handle_more_menu_modal(  # type: ignore[attr-defined]
            {
                "ocr_results": [
                    {"text": "商店", "box": (460, 760, 600, 800)},
                    {"text": "持有物", "box": (470, 900, 610, 940)},
                ]
            }
        )

        self.assertTrue(result.success)
        self.assertTrue(task._is_action_done("holdings_entered"))  # type: ignore[attr-defined]
        _, kwargs = tap_text_mock.call_args
        self.assertTrue(kwargs.get("exact"))


if __name__ == "__main__":
    unittest.main()
