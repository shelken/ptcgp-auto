# -*- coding: utf-8 -*-

import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast
from unittest.mock import patch

src_dir = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(src_dir))

from ptcgp_auto_v2.core.hooks import HookContext, HookResult
from ptcgp_auto_v2.hooks.gift_hooks import ClaimGiftsPreHook, SendCardWakeTargetPostHook


class TestSendCardWakeTargetPostHook(unittest.TestCase):
    def setUp(self):
        self.hook = SendCardWakeTargetPostHook()

    @patch("ptcgp_auto_v2.hooks.gift_hooks.GiftRecordService")
    def test_wake_target_when_send_success_and_target_not_sent_back(
        self,
        record_service_mock,
    ):
        task = SimpleNamespace(
            task_type="send_card_daily",
            _gift_sent_success=True,
            _target_account_id=6,
        )
        context = HookContext(
            device=cast(Any, SimpleNamespace()),
            account=cast(Any, SimpleNamespace(id=1, friend_id="1111222233334444")),
            task=cast(Any, task),
            executor=cast(Any, SimpleNamespace()),
        )

        record_service_mock.is_daily_success.return_value = False
        result, data = self.hook.run(context)

        self.assertEqual(HookResult.CONTINUE, result)
        self.assertEqual({}, data)
        record_service_mock.ensure_send_card_daily_pending.assert_called_once_with(
            account_id=6
        )

    @patch("ptcgp_auto_v2.hooks.gift_hooks.GiftRecordService")
    def test_skip_wake_when_target_already_sent_back(self, record_service_mock):
        task = SimpleNamespace(
            task_type="send_card_daily",
            _gift_sent_success=True,
            _target_account_id=6,
        )
        context = HookContext(
            device=cast(Any, SimpleNamespace()),
            account=cast(Any, SimpleNamespace(id=1, friend_id="1111222233334444")),
            task=cast(Any, task),
            executor=cast(Any, SimpleNamespace()),
        )

        record_service_mock.is_daily_success.return_value = True
        result, data = self.hook.run(context)

        self.assertEqual(HookResult.CONTINUE, result)
        self.assertEqual({}, data)
        record_service_mock.ensure_send_card_daily_pending.assert_not_called()

    @patch("ptcgp_auto_v2.hooks.gift_hooks.GiftRecordService")
    def test_skip_when_current_task_not_sent_success(self, record_service_mock):
        task = SimpleNamespace(
            task_type="send_card_daily",
            _gift_sent_success=False,
            _target_account_id=6,
        )
        context = HookContext(
            device=cast(Any, SimpleNamespace()),
            account=cast(Any, SimpleNamespace(id=1, friend_id="1111222233334444")),
            task=cast(Any, task),
            executor=cast(Any, SimpleNamespace()),
        )

        result, data = self.hook.run(context)

        self.assertEqual(HookResult.CONTINUE, result)
        self.assertEqual({}, data)
        record_service_mock.is_daily_success.assert_not_called()
        record_service_mock.ensure_send_card_daily_pending.assert_not_called()


class TestClaimGiftsPreHook(unittest.TestCase):
    def setUp(self):
        self.hook = ClaimGiftsPreHook()

    @patch("ptcgp_auto_v2.hooks.gift_hooks.TaskInstanceRepository")
    def test_continue_when_claim_completed_today(self, repo_cls):
        from datetime import datetime

        repo = repo_cls.return_value
        repo.get_by_account_and_type.return_value = SimpleNamespace(
            status="completed",
            last_completed_at=datetime.now(),
        )
        context = HookContext(
            device=cast(Any, SimpleNamespace()),
            account=cast(Any, SimpleNamespace(id=2)),
            task=cast(Any, SimpleNamespace()),
            executor=cast(Any, SimpleNamespace()),
        )

        result, data = self.hook.run(context)
        self.assertEqual(HookResult.CONTINUE, result)
        self.assertEqual({}, data)

    @patch("ptcgp_auto_v2.hooks.gift_hooks.TaskInstanceRepository")
    def test_insert_claim_task_when_not_completed_today(self, repo_cls):
        repo = repo_cls.return_value
        saved = {"called": False}

        def _save():
            saved["called"] = True

        instance = SimpleNamespace(status="failed", last_completed_at=None, save=_save)
        repo.get_by_account_and_type.return_value = instance
        context = HookContext(
            device=cast(Any, SimpleNamespace()),
            account=cast(Any, SimpleNamespace(id=2)),
            task=cast(Any, SimpleNamespace()),
            executor=cast(Any, SimpleNamespace()),
        )

        result, data = self.hook.run(context)
        self.assertEqual(HookResult.INSERT_TASK, result)
        self.assertEqual("claim_gifts", data.get("task_type"))
        self.assertTrue(saved["called"])


if __name__ == "__main__":
    unittest.main()
