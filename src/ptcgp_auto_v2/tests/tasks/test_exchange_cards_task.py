# -*- coding: utf-8 -*-

import sys
import unittest
from datetime import datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast
from unittest.mock import Mock, patch

src_dir = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(src_dir))

from ptcgp_auto_v2.core.task_base import ActionResult
from ptcgp_auto_v2.tasks.exchange_cards import ExchangeCardsTask
from ptcgp_auto_v2.tests.fake_adb import FakeAdb


class DummyPageDetector:
    """交换任务测试页面检测桩。"""

    def get_last_page_context(self):
        return None, []

    def capture(self):
        return None, []


class TestExchangeCardsTask(unittest.TestCase):
    def setUp(self):
        self.task = ExchangeCardsTask(
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

    def _prepare_sending_request(self):
        request = SimpleNamespace(
            id=10,
            from_account_id=1,
            to_account_id=2,
            to_friend_id="1234567890123456",
            target_card_id=1001,
            target_card_rarity="R",
            status="sending",
            next_check_at=None,
            expire_at=datetime.now() + timedelta(minutes=30),
            cancel_reason=None,
            updated_at=None,
        )
        task = cast(Any, self.task)
        task._request_repo = SimpleNamespace(
            get_active_by_account=Mock(return_value=request),
            mark_failed=Mock(),
            mark_sended=Mock(side_effect=lambda req, next_check_at: req),
            mark_canceled=Mock(),
            mark_completed=Mock(),
            update=Mock(return_value=request),
        )
        task._account_card_repo = SimpleNamespace(
            get=Mock(
                return_value=SimpleNamespace(
                    count=1, yolo_conf=None, hash_similarity=None
                )
            ),
            upsert=Mock(),
        )
        task._card_repo = SimpleNamespace(
            get_by_id=Mock(
                return_value=SimpleNamespace(
                    id=1001, set_code="A1", number=1, name="妙蛙種子"
                )
            )
        )
        task._account_repo = SimpleNamespace(
            get_by_id=Mock(return_value=SimpleNamespace(nickname="skn5"))
        )
        return request

    @patch(
        "ptcgp_auto_v2.tasks.exchange_cards.resolve_card_name", return_value="妙蛙種子"
    )
    @patch("ptcgp_auto_v2.tasks.exchange_cards.tap_ok")
    def test_proposed_done_popup_marks_sended_and_delay(
        self, tap_ok_mock, _resolve_name
    ):
        """提议完成弹窗应写入 sended 并进入当前任务等待窗口。"""
        request = self._prepare_sending_request()
        tap_ok_mock.return_value = ActionResult.ok(wait=0.1)

        self.task.on_start()
        result = cast(Any, self.task)._handle_proposed_done_popup({"ocr_results": []})

        self.assertTrue(result.success)
        self.assertFalse(self.task.is_completed())
        cast(Any, self.task)._request_repo.mark_sended.assert_called_once()
        self.assertEqual("sending", request.status)
        self.assertIsNone(request.expire_at)

    def test_on_start_fails_when_account_not_past_14_days(self):
        """账号未过14天冷静期时，请求应失败并结束任务。"""
        task = cast(Any, self.task)
        request = SimpleNamespace(
            id=20,
            from_account_id=1,
            to_account_id=2,
            to_friend_id="1234567890123456",
            target_card_id=2001,
            target_card_rarity="R",
            status="sended",
            next_check_at=None,
            expire_at=datetime.now() + timedelta(minutes=30),
            updated_at=None,
        )
        repo = SimpleNamespace(
            get_active_by_account=Mock(return_value=request),
            mark_failed=Mock(return_value=request),
        )
        task._request_repo = repo
        task._card_repo = SimpleNamespace(get_by_id=Mock(return_value=None))
        task._account_repo = SimpleNamespace(get_by_id=Mock(return_value=None))

        with patch(
            "ptcgp_auto_v2.tasks.exchange_cards.is_account_past_days",
            return_value=False,
        ):
            task.on_start()

        self.assertTrue(task.is_completed())
        self.assertTrue(task.should_preserve_last_completed_at())
        repo.mark_failed.assert_called_once()

    def test_on_start_skips_when_same_day_pending_cooldown(self):
        """同日待过冷冻期时，应跳过而不是失败。"""
        task = cast(Any, self.task)
        request = SimpleNamespace(
            id=21,
            from_account_id=1,
            to_account_id=2,
            to_friend_id="1234567890123456",
            target_card_id=2001,
            target_card_rarity="R",
            status="sended",
            next_check_at=None,
            expire_at=datetime.now() + timedelta(minutes=30),
            updated_at=None,
        )
        repo = SimpleNamespace(
            get_active_by_account=Mock(return_value=request),
            mark_failed=Mock(return_value=request),
        )
        task._request_repo = repo

        with (
            patch(
                "ptcgp_auto_v2.tasks.exchange_cards.is_account_past_days",
                return_value=False,
            ),
            patch(
                "ptcgp_auto_v2.tasks.exchange_cards.is_account_pending_same_day_cooldown",
                return_value=True,
            ),
        ):
            task.on_start()

        self.assertTrue(task.is_completed())
        self.assertTrue(task.was_skipped())
        self.assertEqual("账号未过14天冷冻期（同日待到期）", task._skip_reason)
        repo.mark_failed.assert_not_called()

    @patch("ptcgp_auto_v2.tasks.exchange_cards.tap_ok")
    def test_locked_popup_should_skip(self, tap_ok_mock):
        """交换未解锁弹窗应点击 OK 并跳过。"""
        task = cast(Any, self.task)
        task._ctx.runtime.current_request = SimpleNamespace(id=1)
        tap_ok_mock.return_value = ActionResult.ok(wait=0.1)

        result = task.handle_page("exchange_locked_popup", {"ocr_results": []})

        self.assertTrue(result.success)
        self.assertTrue(task.is_completed())
        self.assertTrue(task.was_skipped())
        self.assertEqual("交换功能未解锁（14天冷冻期未到）", task._skip_reason)

    @patch(
        "ptcgp_auto_v2.tasks.exchange_cards.resolve_card_name", return_value="妙蛙種子"
    )
    @patch("ptcgp_auto_v2.tasks.exchange_cards.tap_template")
    def test_waiting_page_sets_window_and_refresh_to_main(
        self,
        tap_template_mock,
        _resolve_name,
    ):
        """进入等待页应启动5分钟窗口，并返回主页刷新状态。"""
        request = self._prepare_sending_request()
        request.status = "sended"
        request.expire_at = None
        tap_template_mock.return_value = ActionResult.ok(wait=0.1)

        self.task.on_start()
        result = cast(Any, self.task)._handle_waiting_page({"ocr_results": []})

        self.assertTrue(result.success)
        self.assertFalse(self.task.is_completed())
        self.assertIsNotNone(request.expire_at)
        cast(Any, self.task)._request_repo.update.assert_called_once()

    @patch(
        "ptcgp_auto_v2.tasks.exchange_cards.resolve_card_name", return_value="妙蛙種子"
    )
    @patch("ptcgp_auto_v2.tasks.exchange_cards.tap_template")
    def test_waiting_page_timeout_should_set_cancel_intent(
        self,
        tap_template_mock,
        _resolve_name,
    ):
        """等待超时后应写入取消意图，不再走刷新。"""
        request = self._prepare_sending_request()
        request.status = "sended"
        request.expire_at = datetime.now() - timedelta(seconds=1)
        request.cancel_reason = None
        tap_template_mock.return_value = None
        cast(Any, self.task)._action_cache["waiting_window_started"] = True

        self.task.on_start()
        result = cast(Any, self.task)._handle_waiting_page({"ocr_results": []})

        self.assertTrue(result.success)
        self.assertIsNotNone(request.cancel_reason)
        self.assertIn("超时", cast(str, request.cancel_reason))
        cast(Any, self.task)._request_repo.update.assert_called_once()

    @patch(
        "ptcgp_auto_v2.tasks.exchange_cards.resolve_card_name", return_value="妙蛙種子"
    )
    def test_on_start_should_cancel_when_sending_expired(self, _resolve_name):
        """sending 请求过期后应在 on_start 直接取消。"""
        request = self._prepare_sending_request()
        request.status = "sending"
        request.expire_at = datetime.now() - timedelta(minutes=1)

        self.task.on_start()

        self.assertTrue(self.task.is_completed())
        cast(Any, self.task)._request_repo.mark_canceled.assert_called_once()

    @patch(
        "ptcgp_auto_v2.tasks.exchange_cards.resolve_card_name", return_value="妙蛙種子"
    )
    def test_on_start_should_set_cancel_intent_when_sended_expired(self, _resolve_name):
        """sended 请求过期后应在 on_start 写入 cancel_reason 并继续取消链路。"""
        request = self._prepare_sending_request()
        request.status = "sended"
        request.expire_at = datetime.now() - timedelta(minutes=1)
        request.cancel_reason = None

        self.task.on_start()

        self.assertEqual("等待对方回应超时（5分钟），自动取消", request.cancel_reason)
        cast(Any, self.task)._request_repo.update.assert_called_once()

    @patch("ptcgp_auto_v2.tasks.exchange_cards.tap_ok")
    def test_canceled_done_popup_should_mark_failed_when_timeout(self, tap_ok_mock):
        """超时取消完成后应标记 failed。"""
        task = cast(Any, self.task)
        request = self._prepare_sending_request()
        request.cancel_reason = "等待对方回应超时（5分钟），自动取消"
        task._ctx.runtime.current_request = request
        tap_ok_mock.return_value = ActionResult.ok(wait=0.1)

        result = task._handle_canceled_done_popup({"ocr_results": []})

        self.assertTrue(result.success)
        task._request_repo.mark_failed.assert_called_once()

    @patch("ptcgp_auto_v2.tasks.exchange_cards.tap_ok")
    def test_receive_start_popup_should_not_complete_immediately(self, tap_ok_mock):
        """开始交换弹窗点击OK后不应立即完成，应等待滑卡页完成。"""
        task = cast(Any, self.task)
        request = self._prepare_sending_request()
        request.status = "sended"
        task._ctx.runtime.current_request = request
        tap_ok_mock.return_value = ActionResult.ok(wait=0.1)

        result = task._handle_receive_start_popup({"ocr_results": []})

        self.assertTrue(result.success)
        self.assertFalse(task.is_completed())
        task._request_repo.mark_completed.assert_not_called()

    @patch("ptcgp_auto_v2.tasks.exchange_cards.swipe_card_register")
    def test_exchange_swipe_page_should_finalize_success(self, swipe_mock):
        """交换滑卡页完成后应标记completed并扣减发送方库存。"""
        task = cast(Any, self.task)
        request = self._prepare_sending_request()
        request.status = "sended"
        request.target_card_id = 1001
        request.from_account_id = 1
        request.to_account_id = 2
        task._ctx.runtime.current_request = request
        swipe_mock.return_value = ActionResult.ok(wait=0.1)

        result = task._handle_exchange_swipe_page({"ocr_results": []})

        self.assertTrue(result.success)
        self.assertTrue(task.is_completed())
        task._request_repo.mark_completed.assert_called_once()
        task._account_card_repo.upsert.assert_called_once()

    def test_choose_friend_should_fail_when_target_row_is_in_exchange(self):
        """已验证好友若同行显示交换中，应直接失败本次交换请求。"""
        task = cast(Any, self.task)
        request = self._prepare_sending_request()
        task._ctx.runtime.current_request = request
        task._ctx.friend_flow.friend_verified = True
        task._friend_helper = SimpleNamespace(
            find_send_box_by_anchor=Mock(return_value=None),
            find_box_by_anchor=Mock(return_value=(800, 1100, 860, 1180)),
            scroll_or_fail=Mock(return_value=ActionResult.wait(0.5)),
        )

        result = task._handle_choose_friend({"ocr_results": []})

        self.assertTrue(result.success)
        task._request_repo.mark_failed.assert_called_once()

    @patch("ptcgp_auto_v2.tasks.exchange_cards.tap_text_exact")
    @patch("ptcgp_auto_v2.tasks.exchange_cards.is_text_visible")
    def test_sending_with_sended_ui_should_enter_cancel_flow_first(
        self,
        is_text_visible_mock,
        tap_text_exact_mock,
    ):
        """sending 若检测到已在等待回应，应先进入取消链路。"""
        request = self._prepare_sending_request()
        request.status = "sending"
        task = cast(Any, self.task)
        task._ctx.runtime.current_request = request
        is_text_visible_mock.side_effect = [True, True]
        tap_text_exact_mock.return_value = ActionResult.ok(wait=0.1)

        result = task._handle_exchange_page_main({"ocr_results": []})

        self.assertTrue(result.success)
        self.assertTrue(task._ctx.runtime.recover_before_send)

    @patch("ptcgp_auto_v2.tasks.exchange_cards.tap_ok")
    def test_canceled_done_popup_should_continue_when_recover_before_send(
        self, tap_ok_mock
    ):
        """恢复重发场景取消完成后不应结束任务，应继续后续发送流程。"""
        task = cast(Any, self.task)
        request = self._prepare_sending_request()
        request.status = "sending"
        request.cancel_reason = "dummy"
        task._ctx.runtime.current_request = request
        task._ctx.runtime.recover_before_send = True
        tap_ok_mock.return_value = ActionResult.ok(wait=0.1)

        result = task._handle_canceled_done_popup({"ocr_results": []})

        self.assertTrue(result.success)
        self.assertFalse(task.is_completed())
        self.assertTrue(task._ctx.runtime.recover_before_send)
        self.assertTrue(task._is_action_done("recover_cancel_done_clicked"))
        task._request_repo.update.assert_called_once()

    def test_handle_page_should_clear_recover_flag_after_exit_canceled_done(self):
        """离开取消完成页面后应清理恢复标记，进入正常重发流程。"""
        task = cast(Any, self.task)
        request = self._prepare_sending_request()
        request.status = "sending"
        task._ctx.runtime.current_request = request
        task._ctx.runtime.recover_before_send = True
        task._action_cache["recover_cancel_done_clicked"] = True

        with patch.object(
            task, "_handle_exchange_page_main", return_value=ActionResult.ok(wait=0.1)
        ):
            result = task.handle_page("exchange_page_main", {"ocr_results": []})

        self.assertTrue(result.success)
        self.assertFalse(task._ctx.runtime.recover_before_send)

    @patch("ptcgp_auto_v2.tasks.exchange_cards.tap_text_exact")
    @patch("ptcgp_auto_v2.tasks.exchange_cards.is_text_visible")
    def test_sended_on_main_should_click_exchange_when_confirm_missing(
        self,
        is_text_visible_mock,
        tap_text_exact_mock,
    ):
        """sended 在主页缺少确认时，应点击交换进入详情页刷新状态。"""
        request = self._prepare_sending_request()
        request.status = "sended"
        task = cast(Any, self.task)
        task._ctx.runtime.current_request = request
        is_text_visible_mock.return_value = False
        tap_text_exact_mock.return_value = ActionResult.ok(wait=0.1)

        result = task._handle_exchange_page_main({"ocr_results": []})

        self.assertTrue(result.success)
        task._request_repo.mark_canceled.assert_not_called()

    @patch("ptcgp_auto_v2.tasks.exchange_cards.tap_text_exact")
    @patch("ptcgp_auto_v2.tasks.exchange_cards.is_text_visible")
    def test_sended_on_main_should_wait_when_no_entry_found(
        self,
        is_text_visible_mock,
        tap_text_exact_mock,
    ):
        """sended 在主页无入口时，应等待重试而不是直接取消。"""
        request = self._prepare_sending_request()
        request.status = "sended"
        task = cast(Any, self.task)
        task._ctx.runtime.current_request = request
        is_text_visible_mock.return_value = False
        tap_text_exact_mock.return_value = None

        result = task._handle_exchange_page_main({"ocr_results": []})

        self.assertTrue(result.success)
        task._request_repo.mark_canceled.assert_not_called()
        task._request_repo.update.assert_not_called()

    @patch("ptcgp_auto_v2.tasks.exchange_cards.is_text_visible")
    def test_exchange_main_should_tap_bottom_exchange_button_only(
        self,
        is_text_visible_mock,
    ):
        """交换主页存在多个同文案时，应点击下方按钮而不是页头标题。"""
        request = self._prepare_sending_request()
        task = cast(Any, self.task)
        task._ctx.runtime.current_request = request
        is_text_visible_mock.side_effect = [False, False]

        result = task._handle_exchange_page_main(
            {
                "ocr_results": [
                    {"text": "交換", "box": (98, 150, 158, 182)},
                    {"text": "紀錄", "box": (500, 1140, 560, 1180)},
                    {"text": "交換", "box": (320, 970, 396, 1032)},
                ]
            }
        )

        self.assertTrue(result.success)
        self.assertEqual(task.adb.tap_points[-1], (358, 1001))


if __name__ == "__main__":
    unittest.main()
