# -*- coding: utf-8 -*-

import sys
import unittest
from datetime import datetime
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

    @patch("ptcgp_auto_v2.tasks.exchange_cards.tap_text_exact")
    def test_exchange_cards_sending_success_marks_sended(self, tap_text_exact_mock):
        """sending 阶段送出成功后标记 sended。"""
        repo = SimpleNamespace()
        task = cast(Any, self.task)
        request = SimpleNamespace(
            id=10,
            from_account_id=1,
            status="sending",
            next_check_at=None,
            updated_at=None,
        )
        repo.get_active_by_account = Mock(return_value=request)
        repo.update = Mock(return_value=request)
        task._request_repo = repo
        tap_text_exact_mock.return_value = ActionResult.ok(wait=0.1)

        task.on_start()
        result = task._handle_exchange_target_page({"ocr_results": []})

        self.assertTrue(result.success)
        self.assertEqual("sended", request.status)
        repo.update.assert_called_once()


if __name__ == "__main__":
    unittest.main()
