import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast
from unittest.mock import Mock, call

src_dir = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(src_dir))

from ptcgp_auto_v2.tasks.collect_account_cards import CollectAccountCardsTask


def _new_task_stub() -> Any:
    """构造仅用于私有方法测试的任务桩对象。"""
    return cast(Any, CollectAccountCardsTask.__new__(CollectAccountCardsTask))


class TestCollectAccountCardsTask(unittest.TestCase):
    def test_flush_pending_cards_keeps_existing_count(self):
        task = _new_task_stub()
        task._account = SimpleNamespace(id=1)
        task._pending_cards = {11: (0.91, 0.82), 22: (0.73, 0.65)}
        task._pending_order = [11, 22]

        repo = Mock()
        repo.get.side_effect = (
            lambda account_id, card_id: SimpleNamespace(count=5)
            if card_id == 22
            else None
        )
        task._account_card_repo = repo

        task._flush_pending_cards()

        repo.upsert.assert_has_calls(
            [
                call(
                    account_id=1,
                    card_id=22,
                    count=5,
                    yolo_conf=0.73,
                    hash_similarity=0.65,
                ),
                call(
                    account_id=1,
                    card_id=11,
                    count=1,
                    yolo_conf=0.91,
                    hash_similarity=0.82,
                ),
            ]
        )
        self.assertEqual(2, repo.upsert.call_count)

    def test_scan_current_page_deduplicates_by_highest_similarity(self):
        task = _new_task_stub()
        task._account = SimpleNamespace(id=1)
        task._consecutive_all_owned = 0
        task._pending_cards = {}
        task._pending_order = []

        card_a = SimpleNamespace(id=101, rarity="SR")
        card_b = SimpleNamespace(id=202, rarity="AR")

        task._card_repo = Mock()
        task._card_repo.get_card_by_set_and_number.side_effect = [
            card_a,
            card_a,
            card_b,
        ]

        task._account_card_repo = Mock()
        task._account_card_repo.get.return_value = SimpleNamespace(count=1)

        task.card_recognizer = Mock()
        task.card_recognizer.scan.return_value = [
            SimpleNamespace(
                set_code="A1", card_number=1, confidence=0.4, similarity=0.5
            ),
            SimpleNamespace(
                set_code="A1", card_number=1, confidence=0.9, similarity=0.8
            ),
            SimpleNamespace(
                set_code="A1", card_number=2, confidence=0.7, similarity=0.6
            ),
        ]

        signature = task._scan_current_page()

        self.assertEqual("A1:1|A1:1|A1:2", signature)
        self.assertEqual(1, task._consecutive_all_owned)
        self.assertEqual([101, 202], task._pending_order)
        self.assertEqual((0.9, 0.8), task._pending_cards[101])
        self.assertEqual((0.7, 0.6), task._pending_cards[202])

    def test_scan_current_page_empty_result_resets_counter(self):
        task = _new_task_stub()
        task._account = SimpleNamespace(id=1)
        task._consecutive_all_owned = 2
        task._account_card_repo = Mock()
        task._card_repo = Mock()
        task.card_recognizer = Mock()
        task.card_recognizer.scan.return_value = []

        signature = task._scan_current_page()

        self.assertIsNone(signature)
        self.assertEqual(0, task._consecutive_all_owned)

    def test_is_arrow_up_for_sort_respects_scaled_tolerance(self):
        task = _new_task_stub()
        task.adb = SimpleNamespace(scaled_y=lambda value: value)

        target_box = (100, 100, 200, 140)
        arrow_near = (210, 116, 230, 146)
        arrow_far = (210, 200, 230, 230)

        self.assertTrue(task._is_arrow_up_for_sort(target_box, arrow_near))
        self.assertFalse(task._is_arrow_up_for_sort(target_box, arrow_far))


if __name__ == "__main__":
    unittest.main()
