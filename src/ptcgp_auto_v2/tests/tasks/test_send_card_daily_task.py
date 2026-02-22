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
    @patch(
        "ptcgp_auto_v2.tasks.send_card_daily.is_account_pending_same_day_cooldown",
        return_value=True,
    )
    def test_on_start_skip_when_in_cooldown_but_same_day(
        self, _same_day_mock, pairing_service_mock
    ):
        task = cast(Any, self.task)
        now = datetime.now().replace(minute=0, second=0, microsecond=0)
        task.account.created_at = now - timedelta(days=14) + timedelta(hours=1)
        pairing_service_mock.is_account_past_cooldown.return_value = False

        task.on_start()

        self.assertTrue(task.is_completed())
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

        self.assertTrue(task.is_completed())
        self.assertTrue(task.was_skipped())
        self.assertEqual("无可用送卡目标", task._skip_reason)
        record_service_mock.ensure_daily_record.assert_not_called()

    @patch("ptcgp_auto_v2.tasks.send_card_daily.tap_ok")
    @patch("ptcgp_auto_v2.tasks.send_card_daily.GiftRecordService.update_status")
    def test_locked_popup_should_skip_and_mark_completed(
        self, update_status_mock, tap_ok_mock
    ):
        task = cast(Any, self.task)
        task._record = SimpleNamespace()
        tap_ok_mock.return_value = ActionResult.ok(wait=0.1)

        result = task._handle_exchange_locked_popup({"ocr_results": [{"text": "OK"}]})

        self.assertTrue(result.success)
        self.assertTrue(task.is_completed())
        self.assertTrue(task.was_skipped())
        self.assertEqual("分送功能未解锁（14天冷冻期未到）", task._skip_reason)
        update_status_mock.assert_called_once_with(
            task._record,
            status="completed_no_target",
            error_code="FEATURE_LOCKED",
            error_message="分送功能未解锁（14天冷冻期未到）",
        )

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
    def test_choose_friend_should_click_search_plus_before_send(self, tap_box_mock):
        task = cast(Any, self.task)
        task._friend_flow.nickname = "skn4"
        task._friend_flow.friend_verified = False
        task._friend_helper = SimpleNamespace(
            update_signature_and_check_stable=lambda _ocr: False,
            find_plus_for_nickname=lambda _ocr, _nick: (900, 360, 980, 430),
            tap_plus_and_wait_profile=lambda _box: ActionResult.ok(wait=0.1),
            scroll_or_fail=lambda: ActionResult.ok(wait=0.1),
            check_scroll_bottom=lambda: False,
            get_next_probe_box=lambda: None,
        )
        tap_box_mock.return_value = ActionResult.ok(wait=0.1)

        result = task._handle_choose_friend({"ocr_results": []})

        self.assertTrue(result.success)
        tap_box_mock.assert_not_called()

    @patch("ptcgp_auto_v2.tasks.send_card_daily.tap_box")
    def test_choose_friend_should_click_send_after_friend_verified(self, tap_box_mock):
        task = cast(Any, self.task)
        task._friend_flow.friend_verified = True
        task._friend_helper = SimpleNamespace(
            update_signature_and_check_stable=lambda _ocr: False,
            find_send_box_by_anchor=lambda _ocr: (760, 520, 890, 570),
            scroll_or_fail=lambda: ActionResult.ok(wait=0.1),
            check_scroll_bottom=lambda: False,
            get_next_probe_box=lambda: None,
        )
        tap_box_mock.return_value = ActionResult.ok(wait=0.1)

        result = task._handle_choose_friend({"ocr_results": []})

        self.assertTrue(result.success)
        tap_box_mock.assert_called_once_with(task.adb, (760, 520, 890, 570), wait=1.0)

    def test_choose_friend_without_helper_returns_wait(self):
        task = cast(Any, self.task)
        task._friend_helper = None
        result = task._handle_choose_friend({"ocr_results": []})
        self.assertTrue(result.success)

    @patch("ptcgp_auto_v2.tasks.send_card_daily.GiftRecordService.update_status")
    def test_choose_friend_scroll_exhausted_should_skip_and_update_record(
        self, update_status_mock
    ):
        task = cast(Any, self.task)
        task._record = SimpleNamespace()
        task._friend_helper = SimpleNamespace(
            update_signature_and_check_stable=lambda _ocr: True,
            scroll_or_fail=lambda: task._skip_without_send(
                skip_reason="好友列表遍历完成未找到可送目标",
                record_status="completed_no_target",
                error_code="TARGET_LIST_EXHAUSTED",
            ),
        )

        result = task._handle_choose_friend({"ocr_results": []})

        self.assertTrue(result.success)
        self.assertTrue(task.was_skipped())
        self.assertEqual("好友列表遍历完成未找到可送目标", task._skip_reason)
        update_status_mock.assert_called_once()

    @patch("ptcgp_auto_v2.tasks.send_card_daily.GiftRecordService.update_status")
    def test_choose_friend_should_skip_when_no_friends_text_visible(
        self, update_status_mock
    ):
        task = cast(Any, self.task)
        task._record = SimpleNamespace()
        task._friend_helper = SimpleNamespace(
            update_signature_and_check_stable=lambda _ocr: False,
            scroll_or_fail=lambda: ActionResult.ok(wait=0.1),
            check_scroll_bottom=lambda: False,
            get_next_probe_box=lambda: None,
        )

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

    def test_duplicate_nickname_logic_is_delegated_to_friend_helper(self):
        """同名好友选择逻辑已委托 FriendSelectionHelper。"""
        task = cast(Any, self.task)
        helper = SimpleNamespace(
            update_signature_and_check_stable=lambda _ocr: False,
            find_plus_for_nickname=lambda _ocr, _nick: (900, 600, 980, 670),
            tap_plus_and_wait_profile=lambda _box: ActionResult.ok(wait=0.1),
            scroll_or_fail=lambda: ActionResult.ok(wait=0.1),
            check_scroll_bottom=lambda: False,
            get_next_probe_box=lambda: None,
        )
        task._friend_helper = helper
        task._friend_flow.nickname = "skn"

        result = task._handle_choose_friend(
            {
                "ocr_results": [
                    {"text": "skn", "box": (389, 408, 450, 430)},
                    {"text": "skn", "box": (389, 648, 450, 670)},
                ]
            }
        )

        self.assertTrue(result.success)


if __name__ == "__main__":
    unittest.main()
