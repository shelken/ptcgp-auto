# -*- coding: utf-8 -*-

import sys
import unittest
from pathlib import Path
from types import SimpleNamespace

src_dir = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(src_dir))

from ptcgp_auto_v2.infra.page_detector import PageDetector
from ptcgp_auto_v2.tasks.wonder_pick import WonderPickTask


class DummyAdb:
    pass


class DummyOcrEngine:
    def __init__(self, results):
        self._results = results

    def recognize_as_dict(self, screenshot):
        return self._results

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


class TestPageDetectorPriority(unittest.TestCase):
    def test_home_page_priority_before_list(self):
        ocr_results = [
            {"text": "商店/兌換處", "box": (1, 2, 3, 4)},
            {"text": "得卡挑戰", "box": (5, 6, 7, 8)},
        ]
        detector = PageDetector(
            adb=DummyAdb(),
            ocr_engine=DummyOcrEngine(ocr_results),
            template_matcher=SimpleNamespace(),
        )

        detector.load_task_pages(
            [
                {
                    "name": "game_home_main",
                    "identifiers": ["商店", "得卡挑戰"],
                    "match_all": True,
                    "priority": 10,
                },
                {
                    "name": "card_challenge_list",
                    "identifiers": ["得卡挑戰"],
                    "exact_match": True,
                    "priority": 20,
                },
            ]
        )

        page_name, _ = detector.detect(screenshot=object())
        self.assertEqual(page_name, "game_home_main")

    def test_wonder_pick_home_priority(self):
        pages = {item["name"]: item for item in WonderPickTask.pages}
        home_priority = pages["game_home_main"]["priority"]
        list_priority = pages["card_challenge_list"]["priority"]

        self.assertLess(home_priority, list_priority)


if __name__ == "__main__":
    unittest.main()
