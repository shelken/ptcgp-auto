# -*- coding: utf-8 -*-
"""得卡挑战任务测试。"""

import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

src_dir = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(src_dir))

from ptcgp_auto_v2.config.wonder_pick import (  # noqa: E402
    WONDER_PICK_DEFAULT_TARGETS,
    WONDER_PICK_RARITY_COSTS,
)
from ptcgp_auto_v2.core.task_base import ActionResult  # noqa: E402
from ptcgp_auto_v2.infra.yolo_card_recognizer import DetectedCard  # noqa: E402
from ptcgp_auto_v2.tasks.wonder_pick import WonderPickTask  # noqa: E402
from ptcgp_auto_v2.tests.fake_adb import FakeAdb  # noqa: E402


class TestChallengeRarityConfig(unittest.TestCase):
    """测试得卡挑战稀有度配置。"""

    def test_default_targets_contains_supported_rarities(self):
        self.assertEqual(set(WONDER_PICK_DEFAULT_TARGETS), {"SAR", "SR"})

    def test_challenge_costs(self):
        self.assertEqual(WONDER_PICK_RARITY_COSTS["C"], 1)
        self.assertEqual(WONDER_PICK_RARITY_COSTS["U"], 1)
        self.assertEqual(WONDER_PICK_RARITY_COSTS["R"], 2)
        self.assertEqual(WONDER_PICK_RARITY_COSTS["RR"], 3)
        self.assertEqual(WONDER_PICK_RARITY_COSTS["AR"], 3)
        self.assertEqual(WONDER_PICK_RARITY_COSTS["SR"], 4)
        self.assertEqual(WONDER_PICK_RARITY_COSTS["SAR"], 4)


class TestChallengeRarityLogic(unittest.TestCase):
    """测试稀有度优先级逻辑。"""

    def test_sort_rarity_targets_by_priority(self):
        targets = ["R", "SAR", "U", "SR"]
        self.assertEqual(
            WonderPickTask.sort_rarity_targets(targets),
            ["SAR", "SR", "R", "U"],
        )

    def test_pick_best_target_from_found(self):
        targets = ["R", "SR", "U"]
        found = ["R", "U", "SR"]
        self.assertEqual(WonderPickTask.pick_best_target(found, targets), "SR")

    def test_is_stamina_enough(self):
        self.assertTrue(WonderPickTask.is_stamina_enough(4, "SR"))
        self.assertFalse(WonderPickTask.is_stamina_enough(3, "SR"))


class TestChallengeEndMarkers(unittest.TestCase):
    """测试结束标志识别。"""

    def test_end_marker_visible(self):
        ocr_results = [{"text": "已結束", "box": (0, 0, 10, 10)}]
        self.assertTrue(WonderPickTask.has_end_marker(ocr_results))

    def test_no_end_marker(self):
        ocr_results = [{"text": "其他", "box": (0, 0, 10, 10)}]
        self.assertFalse(WonderPickTask.has_end_marker(ocr_results))


class FakeCardRepo:
    def __init__(self, rarity_map: dict[tuple[str, int], str]):
        self._rarity_map = rarity_map

    def get_card_by_set_and_number(
        self,
        set_code: str,
        card_number: int,
        load_packs: bool = False,
    ):
        rarity = self._rarity_map.get((set_code, card_number))
        if not rarity:
            return None
        return SimpleNamespace(id=1, rarity=rarity)


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
        self._card_repo = FakeCardRepo({})
        self._account_card_repo = Mock()

    def _get_wonder_stamina(self):
        return None

    def is_completed(self) -> bool:
        return self._completed

    def handle_page(self, page_name: str, page_info: dict) -> ActionResult:
        return ActionResult.ok(wait=0.0)


class TestWonderPickGroupFlow(unittest.TestCase):
    def test_refresh_active_targets_uses_first_affordable_group(self):
        task = FakeTask()
        task._current_stamina = 4
        task._refresh_active_targets()

        self.assertEqual(task._active_targets, ["SAR", "SR"])
        self.assertEqual(task._active_group_index, 0)

    def test_collect_page_targets_filters_to_configured_rarities(self):
        task = FakeTask()
        task._card_repo = FakeCardRepo({("A", 1): "SR", ("A", 2): "U"})
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
        ]

        result = task._collect_page_targets(detected)

        self.assertEqual(result, [("SR", (100.0, 200.0))])

    def test_pick_target_on_current_page_prefers_highest_in_active_group(self):
        task = FakeTask()
        task._card_repo = FakeCardRepo({("A", 1): "SR", ("A", 2): "SAR"})
        task._active_targets = ["SAR", "SR"]
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
        ]

        with patch.object(task, "_tap_card_center") as mock_tap:
            result = task._pick_target_on_current_page(detected)

        self.assertEqual(result, "SAR")
        mock_tap.assert_called_once_with((300.0, 400.0))

    def test_record_seen_lower_group_tracks_lower_affordable_group(self):
        task = FakeTask()
        task._card_repo = FakeCardRepo({("A", 1): "RR"})
        task._active_group_index = 0
        detected = [
            DetectedCard(
                set_code="A",
                card_number=1,
                confidence=0.9,
                similarity=0.9,
                bbox=(0, 0, 10, 10),
                center=(100.0, 200.0),
            )
        ]

        task._record_seen_lower_group(detected)

        self.assertIsNone(task._seen_lower_group_index)

    def test_advance_scan_group_switches_to_seen_lower_group(self):
        task = FakeTask()
        task._current_stamina = 4
        task._seen_lower_group_index = None

        result = task._advance_scan_group()

        self.assertTrue(result.success)
        self.assertTrue(task._completed)

    def test_advance_scan_group_finishes_when_reverse_scan_done(self):
        task = FakeTask()
        task._reverse_scan = True

        result = task._advance_scan_group()

        self.assertTrue(result.success)
        self.assertTrue(task._completed)

    def test_should_finish_current_group_ignores_end_marker_during_reverse(self):
        task = FakeTask()
        task._reverse_scan = True

        with patch.object(task, "_update_scan_signature", return_value=0):
            result = task._should_finish_current_group(
                detected=[],
                ocr_results=[{"text": "已結束", "box": (0, 0, 10, 10)}],
            )

        self.assertFalse(result)

    def test_handle_list_resets_after_challenge_and_keeps_next_group(self):
        task = FakeTask()
        task._current_stamina = 4
        task._active_targets = ["AR"]
        task._active_group_index = 1
        task._pending_after_challenge = True
        task._selected_rarity = "SR"
        task._get_card_saved = True

        with patch.object(task, "_scan_cards", return_value=[]):
            with patch.object(task, "_pick_target_on_current_page", return_value=None):
                with patch.object(
                    task, "_should_finish_current_group", return_value=False
                ):
                    result = task._handle_list({"ocr_results": []})

        self.assertTrue(result.success)
        self.assertEqual(task._active_targets, ["SAR", "SR"])
        self.assertFalse(task._pending_after_challenge)


class TestWonderPickPopupFlow(unittest.TestCase):
    def test_popup_recover_text_should_skip(self):
        task = FakeTask()
        with patch(
            "ptcgp_auto_v2.tasks.wonder_pick.is_text_visible",
            return_value=True,
        ):
            result = task._handle_popup(
                {"ocr_results": [{"text": "恢復", "box": (0, 0, 10, 10)}]}
            )

        self.assertTrue(result.success)
        self.assertTrue(task._completed)
        self.assertTrue(task._skipped)

    def test_handle_popup_sets_target_pick_index_by_rescan(self):
        task = FakeTask()
        task._selected_rarity = "SR"
        task._card_repo = FakeCardRepo(
            {("A", 1): "AR", ("A", 2): "SR", ("A", 3): "SAR"}
        )
        task._current_stamina = 4

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
                center=(300.0, 200.0),
            ),
            DetectedCard(
                set_code="A",
                card_number=3,
                confidence=0.9,
                similarity=0.9,
                bbox=(0, 0, 10, 10),
                center=(500.0, 200.0),
            ),
        ]

        with patch.object(task, "_scan_cards", return_value=detected):
            with patch(
                "ptcgp_auto_v2.tasks.wonder_pick.tap_ok",
                return_value=ActionResult.ok(wait=0.5),
            ):
                result = task._handle_popup({"ocr_results": []})

        self.assertTrue(result.success)
        self.assertEqual(task._target_pick_index, 2)
        self.assertTrue(task._pending_after_challenge)


class TestWonderPickCardRegister(unittest.TestCase):
    def test_handle_card_register_swipes_up(self):
        task = FakeTask()

        result = task._handle_card_register({"ocr_results": []})

        self.assertTrue(result.success)
        self.assertEqual(1, len(task.adb.swipes))
        start, end, _ = task.adb.swipes[0]
        self.assertEqual(start[0], end[0])
        self.assertGreater(start[1], end[1])


class TestWonderPickGetCardNotify(unittest.TestCase):
    def test_handle_get_card_uses_high_rarity_saver_notify_filter(self):
        task = FakeTask()
        task.bind_account(SimpleNamespace(id=1, display_name="tester"))
        task._card_repo = Mock()
        task._account_card_repo = Mock()
        task._selected_rarity = "SR"

        card = SimpleNamespace(id=101, rarity="SR")
        task._card_repo.get_card_by_set_and_number.return_value = card
        task.card_recognizer = Mock()
        task.card_recognizer.scan.return_value = [
            DetectedCard(
                set_code="A1",
                card_number=1,
                confidence=0.9,
                similarity=0.88,
                bbox=(0, 0, 1, 1),
                center=(10.0, 10.0),
            )
        ]

        with patch("ptcgp_auto_v2.tasks.wonder_pick.get_notifier") as mock_get_notifier:
            with patch(
                "ptcgp_auto_v2.tasks.wonder_pick.save_high_rarity_cards"
            ) as mock_save:
                with patch(
                    "ptcgp_auto_v2.tasks.wonder_pick.tap_text_exact",
                    return_value=ActionResult.ok(wait=0.5),
                ):
                    mock_get_notifier.return_value = Mock()
                    task._handle_get_card(
                        {"ocr_results": [{"text": "點擊來繼續", "box": (0, 0, 10, 10)}]}
                    )

        self.assertTrue(mock_save.called)
        kwargs = mock_save.call_args.kwargs
        self.assertIn("notifier", kwargs)
        self.assertIn("rows", kwargs)
        self.assertEqual("得卡挑战获得稀有卡牌", kwargs.get("notify_message"))


if __name__ == "__main__":
    unittest.main()
