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
from ptcgp_auto_v2.hooks.friend_hooks import (
    EXTERNAL_SENDED_DELAY_SECONDS,
    INTERNAL_SENDED_DELAY_SECONDS,
    FriendPreHook,
)


class TestFriendPreHookDelay(unittest.TestCase):
    def setUp(self):
        self.hook = FriendPreHook(
            target_friend_id="1234567890123456", target_account_id=9
        )
        self.context = HookContext(
            device=cast(Any, SimpleNamespace()),
            account=cast(Any, SimpleNamespace(id=1)),
            task=cast(Any, SimpleNamespace(task_type="exchange_cards")),
            executor=cast(Any, SimpleNamespace()),
        )

    @patch("ptcgp_auto_v2.hooks.friend_hooks.FriendshipService")
    @patch("ptcgp_auto_v2.hooks.friend_hooks.FriendRequestRepository")
    def test_should_delay_for_internal_sended_request(self, repo_cls, service_mock):
        repo_cls.return_value.get_pending_request.return_value = SimpleNamespace(
            status="sended",
            to_account_id=7,
        )
        service_mock.is_friend.return_value = False
        service_mock.expire_add_request_if_needed.return_value = False

        result, data = self.hook.run(self.context)

        self.assertEqual(HookResult.DELAY, result)
        self.assertEqual(INTERNAL_SENDED_DELAY_SECONDS, data.get("delay_seconds"))
        self.assertEqual("等待对方接受好友请求", data.get("reason"))
        service_mock.ensure_manage_friendship_pending.assert_called_once_with(
            account_id=7
        )

    @patch("ptcgp_auto_v2.hooks.friend_hooks.FriendshipService")
    @patch("ptcgp_auto_v2.hooks.friend_hooks.FriendRequestRepository")
    def test_should_delay_for_external_sended_request(self, repo_cls, service_mock):
        repo_cls.return_value.get_pending_request.return_value = SimpleNamespace(
            status="sended",
            to_account_id=None,
        )
        service_mock.is_friend.return_value = False
        service_mock.expire_add_request_if_needed.return_value = False

        result, data = self.hook.run(self.context)

        self.assertEqual(HookResult.DELAY, result)
        self.assertEqual(EXTERNAL_SENDED_DELAY_SECONDS, data.get("delay_seconds"))
        self.assertEqual("等待外部好友接受请求", data.get("reason"))
        service_mock.ensure_manage_friendship_pending.assert_called_once_with(
            account_id=1
        )


if __name__ == "__main__":
    unittest.main()
