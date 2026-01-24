import sys
import unittest
from pathlib import Path
from types import SimpleNamespace

src_dir = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(src_dir))

from ptcgp_auto_v2.infra.page_detector import PageDetector


class DummyAdb:
    pass


class DummyOcrEngine:
    def match_text(self, target, text, exact_match=False):
        target_lower = target.strip().lower()
        target_normalized = "".join(target_lower.split())
        text_lower = text.strip().lower()
        text_normalized = "".join(text_lower.split())
        if exact_match:
            return target_lower == text_lower
        return (
            target_lower == text_lower
            or target_lower in text_lower
            or target_normalized in text_normalized
        )


class TestPageDetectorTextMatch(unittest.TestCase):
    def setUp(self):
        self.detector = PageDetector(
            adb=DummyAdb(),
            ocr_engine=DummyOcrEngine(),
            template_matcher=SimpleNamespace(),
        )

    def test_find_identifier_fuzzy_match(self):
        ocr_results = [
            {"text": "Start   Battle", "box": (1, 2, 3, 4)},
        ]
        result = self.detector._find_identifier(
            identifier="start battle",
            ocr_results=ocr_results,
            exact_match=False,
        )

        self.assertIsNotNone(result)
        self.assertEqual("Start   Battle", result["matched_text"])

    def test_find_identifier_exact_match_rejects_partial(self):
        ocr_results = [
            {"text": "Play Now", "box": (1, 2, 3, 4)},
        ]
        result = self.detector._find_identifier(
            identifier="play",
            ocr_results=ocr_results,
            exact_match=True,
        )

        self.assertIsNone(result)


if __name__ == "__main__":
    unittest.main()
