import sys
import unittest
from pathlib import Path
from typing import cast

src_dir = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(src_dir))

from ptcgp_auto_v2.infra.adb import AdbController
from ptcgp_auto_v2.infra.page_detector import PageDetector
from ptcgp_auto_v2.tasks.fetch_account_info import FetchAccountInfoTask


class TestFetchAccountInfoExtractExchangePoints(unittest.TestCase):
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


if __name__ == "__main__":
    unittest.main()
