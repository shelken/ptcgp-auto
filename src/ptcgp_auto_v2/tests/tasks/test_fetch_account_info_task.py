import sys
import unittest
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, cast
from types import SimpleNamespace
from unittest.mock import patch

src_dir = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(src_dir))

from ptcgp_auto_v2.infra.adb import AdbController
from ptcgp_auto_v2.infra.page_detector import PageDetector
from ptcgp_auto_v2.core.task_base import ActionResult
from ptcgp_auto_v2.tasks.fetch_account_info import FetchAccountInfoTask


class TestFetchAccountInfoExtractExchangePoints(unittest.TestCase):
    @staticmethod
    def _build_adb_stub():
        return cast(
            AdbController,
            SimpleNamespace(
                scaled_y=lambda y: y,
                center_x=lambda: 540,
            ),
        )

    def test_extract_exchange_points_ignores_single_digit(self):
        adb = cast(AdbController, object())
        page_detector = cast(PageDetector, object())
        task = FetchAccountInfoTask(
            adb=adb, recognizer=None, page_detector=page_detector
        )

        ocr = [
            {"text": "9"},
            {"text": "交換"},
            {"text": "149,610"},
        ]

        self.assertEqual(149610, task._extract_exchange_points(ocr))  # type: ignore[attr-defined]

    @patch("ptcgp_auto_v2.tasks.fetch_account_info.tap_community_icon")
    def test_handle_home_skip_exchange_when_in_cooldown(self, tap_community_icon_mock):
        adb = cast(AdbController, object())
        page_detector = cast(PageDetector, object())
        task = FetchAccountInfoTask(
            adb=adb, recognizer=None, page_detector=page_detector
        )
        task.bind_account(
            cast(
                Any,
                SimpleNamespace(
                    created_at=datetime.now() - timedelta(days=3),
                    friend_id="123",
                    nickname="n",
                    exchange_points=None,
                ),
            )
        )
        task._mark_action_done("profile_fetched")  # type: ignore[attr-defined]

        result = task._handle_home({"ocr_results": []})  # type: ignore[attr-defined]

        self.assertTrue(result.success)
        self.assertEqual(0, task._exchange_points)  # type: ignore[attr-defined]
        self.assertTrue(task._is_action_done("exchange_fetched"))  # type: ignore[attr-defined]
        tap_community_icon_mock.assert_not_called()

    def test_extract_exchange_points_returns_none_when_only_single_digits(self):
        adb = cast(AdbController, object())
        page_detector = cast(PageDetector, object())
        task = FetchAccountInfoTask(
            adb=adb, recognizer=None, page_detector=page_detector
        )

        ocr = [
            {"text": "9"},
            {"text": "0"},
        ]

        self.assertIsNone(task._extract_exchange_points(ocr))  # type: ignore[attr-defined]

    def test_extract_exchange_points_ignores_circled_digits(self):
        adb = cast(AdbController, object())
        page_detector = cast(PageDetector, object())
        task = FetchAccountInfoTask(
            adb=adb, recognizer=None, page_detector=page_detector
        )

        ocr = [
            {"text": "④"},
            {"text": "149,610"},
        ]

        self.assertEqual(149610, task._extract_exchange_points(ocr))  # type: ignore[attr-defined]

    def test_extract_pack_hourglass_prefers_right_upper_number(self):
        adb = self._build_adb_stub()
        page_detector = cast(PageDetector, object())
        task = FetchAccountInfoTask(
            adb=adb, recognizer=None, page_detector=page_detector
        )

        ocr = [
            {"text": "9", "box": (43, 164, 60, 184)},
            {"text": "12", "box": (873, 847, 910, 876)},
            {"text": "開包沙漏", "box": (531, 986, 620, 1016)},
        ]

        self.assertEqual(12, task._extract_pack_hourglass(ocr))  # type: ignore[attr-defined]

    @patch("ptcgp_auto_v2.tasks.fetch_account_info.click_close")
    def test_handle_pack_hourglass_popup_should_set_value_and_close(
        self, click_close_mock
    ):
        adb = self._build_adb_stub()
        page_detector = cast(PageDetector, object())
        task = FetchAccountInfoTask(
            adb=adb, recognizer=None, page_detector=page_detector
        )
        click_close_mock.return_value = ActionResult.ok(wait=0.1)

        result = task._handle_pack_hourglass_popup(  # type: ignore[attr-defined]
            {
                "ocr_results": [
                    {"text": "9", "box": (43, 164, 60, 184)},
                    {"text": "12", "box": (873, 847, 910, 876)},
                    {"text": "開包沙漏", "box": (531, 986, 620, 1016)},
                ]
            }
        )

        self.assertTrue(result.success)
        self.assertEqual(12, task._pack_hourglass_count)  # type: ignore[attr-defined]
        self.assertTrue(task._is_action_done("pack_hourglass_fetched"))  # type: ignore[attr-defined]

    @patch("ptcgp_auto_v2.tasks.fetch_account_info.tap_template")
    def test_handle_home_should_keep_trying_pack_hourglass_icon(
        self, tap_template_mock
    ):
        adb = self._build_adb_stub()
        page_detector = cast(PageDetector, object())
        task = FetchAccountInfoTask(
            adb=adb, recognizer=None, page_detector=page_detector
        )
        tap_template_mock.return_value = None

        result = task._handle_home({"ocr_results": []})  # type: ignore[attr-defined]

        self.assertTrue(result.success)
        self.assertFalse(task._is_action_done("pack_hourglass_fetched"))  # type: ignore[attr-defined]
        tap_template_mock.assert_called_once()


if __name__ == "__main__":
    unittest.main()
