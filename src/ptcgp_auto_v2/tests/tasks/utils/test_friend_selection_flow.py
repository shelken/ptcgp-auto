# -*- coding: utf-8 -*-

import sys
import unittest
from pathlib import Path
from typing import Any, cast
from unittest.mock import patch

src_dir = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(src_dir))

from ptcgp_auto_v2.core.task_base import ActionResult
from ptcgp_auto_v2.tasks.utils.friend_selection_flow import (
    FriendSelectionFlow,
    FriendSelectionHelper,
)


class _DummyAdb:
    pass


class _DummyPageDetector:
    def detect(self):
        return "friend_profile", {"ocr_results": [{"text": "dummy"}]}


class TestFriendSelectionFlow(unittest.TestCase):
    @patch("ptcgp_auto_v2.tasks.utils.friend_selection_flow.tap_box")
    def test_tap_plus_should_pass_configured_account_id_to_profile_verification(
        self,
        tap_box_mock,
    ):
        """探测点击 plus 后，应将初始化传入的 account_id 传给详情页核验。"""
        tap_box_mock.return_value = ActionResult.ok(wait=0.1)
        flow = FriendSelectionFlow()
        helper = FriendSelectionHelper(
            adb=cast(Any, _DummyAdb()),
            page_detector=cast(Any, _DummyPageDetector()),
            flow=flow,
            target_friend_id="1234567890123456",
            profile_page_name="profile_page",
            send_text_patterns=["交換"],
            account_id=42,
        )

        with patch.object(
            helper,
            "handle_profile_verification",
            return_value=ActionResult.ok(wait=0.1),
        ) as handle_mock:
            result = helper.tap_plus_and_wait_profile((100, 200, 140, 240))

        self.assertTrue(result.success)
        handle_mock.assert_called_once_with(
            ocr_results=[{"text": "dummy"}],
            account_id=42,
        )


if __name__ == "__main__":
    unittest.main()
