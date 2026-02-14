# -*- coding: utf-8 -*-

import sys
import unittest
from datetime import datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast
from unittest.mock import patch

src_dir = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(src_dir))

from ptcgp_auto_v2.core.task_base import ActionResult
from ptcgp_auto_v2.tasks.send_card_daily import SendCardDailyTask
from ptcgp_auto_v2.hooks.gift_hooks import SendCardWakeTargetPostHook
from ptcgp_auto_v2.tests.fake_adb import FakeAdb


class DummyPageDetector:
    """送卡任务启动阶段测试用页面检测桩。"""

    def find_all_templates(self, template_name, threshold=0.8, scale=1.0):
        return []


class TestSendCardDailyTask(unittest.TestCase):
    def setUp(self):
        self.task = SendCardDailyTask(
            adb=cast(Any, FakeAdb()),
            recognizer=None,
            page_detector=cast(Any, DummyPageDetector()),
        )
        self.task.bind_account(
            cast(
                Any,
                SimpleNamespace(
                    id=1,
                    friend_id="1234567890123456",
                    nickname="acc1",
                    created_at=datetime(2026, 1, 1, 0, 0, 0),
                ),
            )
        )

    @patch("ptcgp_auto_v2.tasks.send_card_daily.GiftPairingService")
    def test_on_start_complete_when_in_cooldown(self, pairing_service_mock):
        pairing_service_mock.is_account_past_cooldown.return_value = False

        self.task.on_start()

        self.assertTrue(self.task.is_completed())
        pairing_service_mock.ensure_pairs_for_account.assert_not_called()

    @patch("ptcgp_auto_v2.tasks.send_card_daily.GiftPairingService")
    def test_on_start_skip_when_in_cooldown_but_same_day(self, pairing_service_mock):
        task = cast(Any, self.task)
        now = datetime.now().replace(minute=0, second=0, microsecond=0)
        task.account.created_at = now - timedelta(days=14) + timedelta(hours=1)
        pairing_service_mock.is_account_past_cooldown.return_value = False

        task.on_start()

        self.assertFalse(task.is_completed())
        self.assertTrue(task.was_skipped())
        self.assertEqual("账号未过14天冷冻期（同日待到期）", task._skip_reason)
        pairing_service_mock.ensure_pairs_for_account.assert_not_called()

    @patch("ptcgp_auto_v2.tasks.send_card_daily.GiftRecordService")
    @patch("ptcgp_auto_v2.tasks.send_card_daily.GiftPairingService")
    def test_on_start_skip_when_no_pair(
        self, pairing_service_mock, record_service_mock
    ):
        task = cast(Any, self.task)
        pairing_service_mock.is_account_past_cooldown.return_value = True
        pairing_service_mock.ensure_pairs_for_account.return_value = None

        task.on_start()

        self.assertFalse(task.is_completed())
        self.assertTrue(task.was_skipped())
        self.assertEqual("无可用送卡目标", task._skip_reason)
        record_service_mock.ensure_daily_record.assert_not_called()

    @patch("ptcgp_auto_v2.tasks.send_card_daily.GiftRecordService")
    @patch("ptcgp_auto_v2.tasks.send_card_daily.GiftPairingService")
    def test_get_pre_hooks_empty_when_start_completed(
        self,
        pairing_service_mock,
        record_service_mock,
    ):
        pairing_service_mock.is_account_past_cooldown.return_value = True
        pairing_service_mock.ensure_pairs_for_account.return_value = None

        self.task.on_start()

        self.assertEqual([], self.task.get_pre_hooks())
        record_service_mock.ensure_daily_record.assert_not_called()

    def test_get_post_hooks_should_include_wake_target_hook(self):
        hooks = self.task.get_post_hooks()
        self.assertEqual(1, len(hooks))
        self.assertIsInstance(hooks[0], SendCardWakeTargetPostHook)

    @patch("ptcgp_auto_v2.tasks.send_card_daily.tap_template")
    def test_select_card_should_not_reopen_filter_when_already_applied(
        self,
        tap_template_mock,
    ):
        task = cast(Any, self.task)
        task._filter_applied = True
        task._tap_target_card_by_scan = lambda detected: ActionResult.ok(wait=0.1)

        result = task._handle_select_card(
            {
                "ocr_results": [
                    {"text": "嘎啦嘎啦", "box": (100, 1500, 200, 1550)},
                ]
            }
        )

        self.assertTrue(result.success)
        tap_template_mock.assert_not_called()

    @patch("ptcgp_auto_v2.tasks.send_card_daily.tap_template")
    def test_select_card_should_open_filter_first_when_not_applied(
        self,
        tap_template_mock,
    ):
        task = cast(Any, self.task)
        task._filter_applied = False
        task._filter_opened = False
        tap_template_mock.return_value = ActionResult.ok(wait=0.1)

        result = task._handle_select_card(
            {
                "ocr_results": [
                    {"text": "嘎啦嘎啦C", "box": (825, 1531, 976, 1570)},
                ]
            }
        )

        self.assertTrue(result.success)
        tap_template_mock.assert_called_once()

    def test_select_card_should_complete_when_scan_not_found_stably(self):
        task = cast(Any, self.task)
        task._filter_applied = True
        task._record = SimpleNamespace()
        task._tap_target_card_by_scan = lambda detected: None
        task.card_recognizer = SimpleNamespace(scan=lambda **kwargs: [])

        with patch(
            "ptcgp_auto_v2.tasks.send_card_daily.GiftRecordService.update_status"
        ) as update_mock:
            result = ActionResult.ok(wait=0.0)
            for _ in range(4):
                result = task._handle_select_card({"ocr_results": []})
            self.assertTrue(result.success)
            self.assertTrue(task.is_completed())
            update_mock.assert_called()

    def test_handle_page_should_mark_filter_applied_when_back_from_modal(self):
        task = cast(Any, self.task)
        task._filter_opened = True
        task._last_page_name = "gift_filter_modal"
        task._prev_page_name = "gift_select_card"

        with patch.object(
            task, "_handle_select_card", return_value=ActionResult.ok(wait=0.1)
        ):
            task.handle_page("gift_select_card", {"ocr_results": []})

        self.assertTrue(task._filter_applied)

    @patch("ptcgp_auto_v2.tasks.send_card_daily.tap_box")
    @patch("ptcgp_auto_v2.tasks.send_card_daily.find_send_box_near_anchor")
    @patch("ptcgp_auto_v2.tasks.send_card_daily.find_target_search_plus_box")
    def test_choose_friend_should_click_search_plus_before_send(
        self,
        find_plus_box_mock,
        find_send_near_anchor_mock,
        tap_box_mock,
    ):
        task = cast(Any, self.task)
        task._target_friend_id = "1234567890123456"
        task._target_nickname = "skn4"
        task._target_friend_verified = False
        find_plus_box_mock.return_value = (900, 360, 980, 430)
        find_send_near_anchor_mock.return_value = (760, 520, 890, 570)
        tap_box_mock.return_value = ActionResult.ok(wait=0.1)

        result = task._handle_choose_friend({"ocr_results": []})

        self.assertTrue(result.success)
        tap_box_mock.assert_called_once_with(task.adb, (900, 360, 980, 430), wait=3)

    @patch("ptcgp_auto_v2.tasks.send_card_daily.tap_box")
    @patch("ptcgp_auto_v2.tasks.send_card_daily.find_send_box_near_anchor")
    def test_choose_friend_should_click_send_after_friend_verified(
        self,
        find_send_near_anchor_mock,
        tap_box_mock,
    ):
        task = cast(Any, self.task)
        task._target_friend_verified = True
        task._verified_row_anchor_y = 520
        task._target_nickname = "skn4"
        find_send_near_anchor_mock.return_value = (760, 520, 890, 570)
        tap_box_mock.return_value = ActionResult.ok(wait=0.1)

        result = task._handle_choose_friend({"ocr_results": []})

        self.assertTrue(result.success)
        tap_box_mock.assert_called_once_with(task.adb, (760, 520, 890, 570), wait=1.0)

    @patch("ptcgp_auto_v2.tasks.send_card_daily.click_close")
    def test_handle_friend_profile_should_verify_target_friend_id(
        self, click_close_mock
    ):
        task = cast(Any, self.task)
        task._target_friend_id = "1234567890123456"
        task._target_friend_verified = False
        task._verified_row_anchor_y = 620
        click_close_mock.return_value = ActionResult.ok(wait=0.1)

        result = task._handle_friend_profile(
            {
                "ocr_results": [
                    {"text": "朋友ID 1234-5678-9012-3456", "box": (100, 100, 420, 140)}
                ]
            }
        )

        self.assertTrue(result.success)
        self.assertTrue(task._target_friend_verified)

    @patch("ptcgp_auto_v2.tasks.send_card_daily.GiftRecordService.update_status")
    def test_friend_list_stable_should_skip_and_update_record(self, update_status_mock):
        task = cast(Any, self.task)
        task._record = SimpleNamespace()
        task._friend_stable_rounds = 99

        result = task._continue_find_target_in_friend_list()

        self.assertTrue(result.success)
        self.assertTrue(task.was_skipped())
        self.assertEqual("好友列表遍历完成未找到可送目标", task._skip_reason)
        update_status_mock.assert_called_once_with(
            task._record,
            status="completed_no_target",
            error_code="TARGET_LIST_EXHAUSTED",
            error_message="好友列表遍历完成未找到可送目标",
        )

    @patch("ptcgp_auto_v2.tasks.send_card_daily.GiftRecordService.update_status")
    def test_choose_friend_should_skip_when_no_friends_text_visible(
        self, update_status_mock
    ):
        task = cast(Any, self.task)
        task._record = SimpleNamespace()
        task._target_friend_verified = False

        result = task._handle_choose_friend(
            {
                "ocr_results": [
                    {"text": "請選擇朋友", "box": (500, 120, 620, 160)},
                    {"text": "沒有朋友。", "box": (450, 880, 620, 930)},
                ]
            }
        )

        self.assertTrue(result.success)
        self.assertTrue(task.was_skipped())
        self.assertEqual("好友列表为空，无法分送卡牌", task._skip_reason)
        update_status_mock.assert_called_once_with(
            task._record,
            status="completed_no_target",
            error_code="NO_FRIENDS",
            error_message="好友列表为空，无法分送卡牌",
        )

    @patch("ptcgp_auto_v2.tasks.send_card_daily.GiftRecordService")
    def test_pair_ordering_should_skip_when_peer_not_attempted(
        self, record_service_mock
    ):
        task = cast(Any, self.task)
        task._record = SimpleNamespace()
        task._target_account_id = 1
        task._target_friend_id = "peer_friend"
        task.account.id = 2
        task.account.friend_id = "me_friend"
        task._get_fixed_card_count = lambda account_id: 1

        record_service_mock.is_daily_success.return_value = False
        record_service_mock.has_daily_attempt.return_value = False

        task._maybe_complete_for_pair_ordering()

        self.assertTrue(task.was_skipped())
        self.assertEqual("双方均有卡，按稳定顺序等待小ID账号先送", task._skip_reason)
        record_service_mock.ensure_send_card_daily_pending.assert_called_once_with(
            account_id=1
        )
        record_service_mock.update_status.assert_called_once_with(
            task._record,
            status="completed_wait_peer_first",
            error_code="WAIT_STABLE_ORDER",
            error_message="双方均有卡，按稳定顺序等待小ID账号先送",
        )

    @patch("ptcgp_auto_v2.tasks.send_card_daily.GiftRecordService")
    def test_pair_ordering_should_continue_when_peer_already_attempted(
        self, record_service_mock
    ):
        task = cast(Any, self.task)
        task._record = SimpleNamespace()
        task._target_account_id = 1
        task._target_friend_id = "peer_friend"
        task.account.id = 2
        task.account.friend_id = "me_friend"
        task._get_fixed_card_count = lambda account_id: 1

        record_service_mock.is_daily_success.return_value = False
        record_service_mock.has_daily_attempt.return_value = True

        task._maybe_complete_for_pair_ordering()

        self.assertFalse(task.was_skipped())
        self.assertFalse(task.is_completed())
        record_service_mock.ensure_send_card_daily_pending.assert_not_called()
        record_service_mock.update_status.assert_not_called()

    @patch("ptcgp_auto_v2.tasks.send_card_daily.extract_friend_id_from_text")
    def test_duplicate_nickname_should_skip_failed_row_and_try_next(self, extract_mock):
        """同名好友场景：第一个验证失败后，应尝试第二个"""
        task = cast(Any, self.task)
        task._target_friend_id = "9999-9999-9999-9999"
        task._target_nickname = "skn"
        task._target_friend_verified = False
        task._failed_plus_rows = set()  # 初始化失败行记录

        # 模拟找到两个加号（同名好友）
        plus_boxes = [
            (900, 360, 980, 430),  # 第一行
            (900, 600, 980, 670),  # 第二行
        ]
        task.page_detector = SimpleNamespace(
            find_all_templates=lambda *args, **kwargs: [
                SimpleNamespace(box=box) for box in plus_boxes
            ]
        )

        # OCR 结果包含两个同名好友
        ocr_results = [
            {"text": "skn", "box": (389, 408, 450, 430)},
            {"text": "skn", "box": (389, 648, 450, 670)},
        ]

        # 第一次提取返回错误的 friend_id
        extract_mock.side_effect = ["1111-1111-1111-1111", "9999-9999-9999-9999"]

        # 第一次调用 _find_target_search_plus_box
        box1 = task._find_target_search_plus_box(ocr_results)
        self.assertEqual(box1, (900, 360, 980, 430))

        # 模拟验证失败，记录失败行
        task._verified_row_anchor_y = (360 + 430) // 2
        task._failed_plus_rows.add(task._verified_row_anchor_y)

        # 第二次调用应返回第二个加号
        box2 = task._find_target_search_plus_box(ocr_results)
        self.assertEqual(box2, (900, 600, 980, 670))

        # 验证失败行已被记录
        self.assertIn((360 + 430) // 2, task._failed_plus_rows)


if __name__ == "__main__":
    unittest.main()
