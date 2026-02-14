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
            get=Mock(return_value=SimpleNamespace(count=1))
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
        """提议完成弹窗应写入 sended 并设置延时复查。"""
        request = self._prepare_sending_request()
        tap_ok_mock.return_value = ActionResult.ok(wait=0.1)

        self.task.on_start()
        result = cast(Any, self.task)._handle_proposed_done_popup({"ocr_results": []})

        self.assertTrue(result.success)
        self.assertTrue(self.task.is_completed())
        cast(Any, self.task)._request_repo.mark_sended.assert_called_once()
        self.assertEqual(300.0, cast(Any, self.task)._ctx.runtime.delay_seconds)
        self.assertEqual(
            "交换请求已送出，等待复查",
            cast(Any, self.task)._ctx.runtime.delay_reason,
        )
        self.assertEqual("sending", request.status)

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
        repo.mark_failed.assert_called_once()

    @patch(
        "ptcgp_auto_v2.tasks.exchange_cards.resolve_card_name", return_value="妙蛙種子"
    )
    def test_waiting_page_sets_delay_when_not_expired(self, _resolve_name):
        """等待页未超时时应更新 next_check_at 并设置 delay。"""
        request = self._prepare_sending_request()
        request.status = "sended"
        request.expire_at = datetime.now() + timedelta(minutes=10)

        self.task.on_start()
        result = cast(Any, self.task)._handle_waiting_page({"ocr_results": []})

        self.assertTrue(result.success)
        self.assertTrue(self.task.is_completed())
        cast(Any, self.task)._request_repo.update.assert_called_once()
        self.assertEqual(300.0, cast(Any, self.task)._ctx.runtime.delay_seconds)


if __name__ == "__main__":
    unittest.main()
