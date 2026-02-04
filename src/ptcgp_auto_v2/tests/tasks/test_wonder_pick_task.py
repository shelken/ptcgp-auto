# -*- coding: utf-8 -*-
"""
得卡挑战任务测试
"""

import sys
import unittest
from unittest.mock import patch
from pathlib import Path
from types import SimpleNamespace

src_dir = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(src_dir))

from ptcgp_auto_v2.tasks.wonder_pick import WonderPickTask
from ptcgp_auto_v2.infra.yolo_card_recognizer import DetectedCard
from ptcgp_auto_v2.config.wonder_pick import (
    WONDER_PICK_DEFAULT_TARGETS,
    WONDER_PICK_RARITY_COSTS,
)
from ptcgp_auto_v2.core.task_base import ActionResult


class TestChallengeRarityConfig(unittest.TestCase):
    """测试得卡挑战稀有度配置"""

    def test_default_targets_contains_supported_rarities(self):
        """测试默认目标稀有度配置"""
        self.assertEqual(set(WONDER_PICK_DEFAULT_TARGETS), {"SAR", "SR", "AR"})

    def test_challenge_costs(self):
        """测试稀有度挑战力消耗配置"""
        self.assertEqual(WONDER_PICK_RARITY_COSTS["C"], 1)
        self.assertEqual(WONDER_PICK_RARITY_COSTS["U"], 1)
        self.assertEqual(WONDER_PICK_RARITY_COSTS["R"], 2)
        self.assertEqual(WONDER_PICK_RARITY_COSTS["RR"], 3)
        self.assertEqual(WONDER_PICK_RARITY_COSTS["AR"], 3)
        self.assertEqual(WONDER_PICK_RARITY_COSTS["SR"], 4)
        self.assertEqual(WONDER_PICK_RARITY_COSTS["SAR"], 4)


class TestChallengeRarityLogic(unittest.TestCase):
    """测试稀有度优先级逻辑"""

    def test_sort_rarity_targets_by_priority(self):
        """测试优先级排序"""
        targets = ["R", "SAR", "U", "SR"]
        sorted_targets = WonderPickTask.sort_rarity_targets(targets)

        self.assertEqual(sorted_targets, ["SAR", "SR", "R", "U"])

    def test_pick_best_target_from_found(self):
        """测试从命中的稀有度选择最高优先级"""
        targets = ["R", "SR", "U"]
        found = ["R", "U", "SR"]
        best = WonderPickTask.pick_best_target(found, targets)

        self.assertEqual(best, "SR")

    def test_is_stamina_enough(self):
        """测试挑战力是否充足"""
        self.assertTrue(WonderPickTask.is_stamina_enough(4, "SR"))
        self.assertFalse(WonderPickTask.is_stamina_enough(3, "SR"))


class TestChallengeEndMarkers(unittest.TestCase):
    """测试结束标志识别"""

    def test_end_marker_visible(self):
        """测试识别已结束或已挑战"""
        ocr_results = [
            {"text": "已結束", "box": (0, 0, 10, 10)},
            {"text": "其他", "box": (0, 0, 10, 10)},
        ]
        self.assertTrue(WonderPickTask.has_end_marker(ocr_results))

    def test_no_end_marker(self):
        """测试未出现结束标志"""
        ocr_results = [{"text": "其他", "box": (0, 0, 10, 10)}]
        self.assertFalse(WonderPickTask.has_end_marker(ocr_results))


class FakeCardRepo:
    def __init__(self, rarity_map: dict[tuple[str, int], str]):
        self._rarity_map = rarity_map

    def get_card_by_set_and_number(self, set_code: str, card_number: int):
        rarity = self._rarity_map.get((set_code, card_number))
        if not rarity:
            return None
        return SimpleNamespace(rarity=rarity)


class TestWonderPickScanLogic(unittest.TestCase):
    def test_build_target_map_filters_and_keeps_first(self):
        detected = [
            DetectedCard(
                set_code="A",
                card_number=1,
                confidence=0.9,
                similarity=0.9,
                bbox=(0, 0, 10, 10),
                center=(100.0, 200.0),
            ),
            DetectedCard(
                set_code="A",
                card_number=2,
                confidence=0.9,
                similarity=0.9,
                bbox=(0, 0, 10, 10),
                center=(300.0, 400.0),
            ),
            DetectedCard(
                set_code="A",
                card_number=3,
                confidence=0.9,
                similarity=0.9,
                bbox=(0, 0, 10, 10),
                center=(500.0, 600.0),
            ),
        ]
        repo = FakeCardRepo({("A", 1): "SR", ("A", 2): "SR", ("A", 3): "SAR"})

        rarity_map, found = WonderPickTask.build_target_map(
            detected, repo, ["SR", "SAR"]
        )

        self.assertEqual(found, ["SR", "SAR"])
        self.assertEqual(rarity_map["SR"], (100.0, 200.0))
        self.assertEqual(rarity_map["SAR"], (500.0, 600.0))

    def test_pick_target_from_map_prefers_highest(self):
        rarity_map = {"SR": (10.0, 10.0), "SAR": (20.0, 20.0)}
        result = WonderPickTask.pick_target_from_map(rarity_map, ["SR", "SAR"])

        self.assertEqual(result, ("SAR", (20.0, 20.0)))

    def test_update_scan_signature_uses_detected_cards(self):
        task = FakeTask()
        detected = [
            DetectedCard(
                set_code="A",
                card_number=1,
                confidence=0.9,
                similarity=0.9,
                bbox=(0, 0, 10, 10),
                center=(100.0, 200.0),
            ),
            DetectedCard(
                set_code="B",
                card_number=2,
                confidence=0.9,
                similarity=0.9,
                bbox=(0, 0, 10, 10),
                center=(300.0, 400.0),
            ),
        ]
        task.card_recognizer = SimpleNamespace(scan=lambda **kwargs: detected)

        count = task._update_scan_signature([{"text": "甲"}])
        self.assertEqual(count, 1)

        count = task._update_scan_signature([{"text": "乙"}])
        self.assertEqual(count, 2)

        new_detected = [
            DetectedCard(
                set_code="C",
                card_number=3,
                confidence=0.9,
                similarity=0.9,
                bbox=(0, 0, 10, 10),
                center=(500.0, 600.0),
            )
        ]
        task.card_recognizer = SimpleNamespace(scan=lambda **kwargs: new_detected)

        count = task._update_scan_signature([{"text": "丙"}])
        self.assertEqual(count, 1)


class FakeAdb:
    def __init__(self):
        self.back_count = 0

    def press_back(self):
        self.back_count += 1

    def swipe_up(self, ratio=0.26, duration=300):
        return None


class FakePageDetector:
    def __init__(self):
        self._last_screenshot = object()
        self._last_ocr_results = []
        self.template_matcher = object()

    def get_last_page_context(self):
        return self._last_screenshot, self._last_ocr_results

    def capture(self, screenshot=None):
        return self._last_screenshot, self._last_ocr_results

    def find_template(self, template_name, threshold=0.8, screenshot=None):
        return None


class FakeTask(WonderPickTask):
    def __init__(self):
        super().__init__(FakeAdb(), recognizer=None, page_detector=FakePageDetector())
        self._current_stamina = None

    def _get_wonder_stamina(self):
        return None


class TestWonderPickHomeFallback(unittest.TestCase):
    def test_list_page_without_stamina_goes_back(self):
        task = FakeTask()

        result = task._handle_list({"ocr_results": []})

        self.assertIsInstance(result, ActionResult)
        self.assertEqual(task.adb.back_count, 1)

    def test_list_page_stamina_not_enough_does_not_skip(self):
        task = FakeTask()
        task._current_stamina = 0
        task._target_rarities = ["SR"]

        with patch.object(task, "_scan_targets", return_value=None):
            result = task._handle_list({"ocr_results": []})

        self.assertIsInstance(result, ActionResult)
        self.assertEqual(task.adb.back_count, 0)
        self.assertFalse(task._skipped)


class TestWonderPickEndMarkerBack(unittest.TestCase):
    def test_end_marker_with_pending_triggers_back(self):
        task = FakeTask()
        task._pending_target = "SR"

        result = task._handle_end_of_list("已出现结束标志")

        self.assertIsInstance(result, ActionResult)
        self.assertEqual(task.adb.back_count, 1)
        self.assertEqual(task._prefer_target, "SR")
        self.assertTrue(task._force_reenter)


class TestWonderPickForceReenter(unittest.TestCase):
    def test_force_reenter_skips_stamina_check(self):
        task = FakeTask()
        task._force_reenter = True
        task._get_wonder_stamina = lambda: 1

        with patch(
            "ptcgp_auto_v2.tasks.wonder_pick.tap_text_exact",
            return_value=ActionResult.ok(wait=0.5),
        ):
            result = task._handle_home({"ocr_results": []})

        self.assertIsInstance(result, ActionResult)
        self.assertFalse(task._skipped)
        self.assertFalse(task._force_reenter)


class TestWonderPickHomeStaminaCache(unittest.TestCase):
    def test_home_uses_cached_stamina_and_enters(self):
        task = FakeTask()
        task._current_stamina = 0
        task._target_rarities = ["SR"]

        with patch(
            "ptcgp_auto_v2.tasks.wonder_pick.tap_text_exact",
            return_value=ActionResult.ok(wait=0.5),
        ) as mock_tap:
            result = task._handle_home({"ocr_results": []})

        self.assertIsInstance(result, ActionResult)
        self.assertFalse(task._skipped)
        self.assertTrue(mock_tap.called)


class TestWonderPickAfterSelect(unittest.TestCase):
    def test_after_select_ends_when_stamina_insufficient(self):
        task = FakeTask()
        task._current_stamina = 0
        task._target_rarities = ["SR"]
        task._mark_action_done("select_card_tapped")

        with patch(
            "ptcgp_auto_v2.tasks.wonder_pick.tap_text_exact",
            return_value=ActionResult.ok(wait=0.5),
        ):
            result = task._handle_select_card({"ocr_results": [{"text": "謝謝"}]})

        self.assertIsInstance(result, ActionResult)
        self.assertTrue(task._completed)


if __name__ == "__main__":
    unittest.main()
