import sys
import unittest
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from ptcgp_auto_v2.core.task_base import ActionResult

src_dir = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(src_dir))

from ptcgp_auto_v2.tasks.manage_friendship import ManageFriendshipTask
from ptcgp_auto_v2.tests.fake_adb import FakeAdb


class FakePageDetector:
    def __init__(self):
        self._green = []
        self._red = []
        self.adb = FakeAdb()

    def find_all_templates(
        self, template_name, screenshot=None, threshold=0.8, scale=1.0
    ):
        if template_name == "icon_green_yes":
            return self._green
        if template_name == "icon_red_no":
            return self._red
        return []


class TestManageFriendshipTask(unittest.TestCase):
    def setUp(self):
        self.adb = FakeAdb()
        self.page_detector = FakePageDetector()
        self.task = ManageFriendshipTask(
            adb=self.adb,
            recognizer=None,
            page_detector=self.page_detector,
        )
        self.task.bind_account(SimpleNamespace(id=1, friend_id="9999000011112222"))

    @patch("ptcgp_auto_v2.tasks.manage_friendship.AccountRepository")
    @patch("ptcgp_auto_v2.tasks.manage_friendship.FriendRequestRepository")
    def test_collect_accept_whitelist_only_with_sender_friend_id(
        self, request_repo_cls, account_repo_cls
    ):
        request_repo = request_repo_cls.return_value
        account_repo = account_repo_cls.return_value

        req_keep = SimpleNamespace(from_account_id=2)
        req_drop = SimpleNamespace(from_account_id=3)
        request_repo.get_by_to_account_and_status.return_value = [req_keep, req_drop]
        account_repo.get_by_id.side_effect = [
            SimpleNamespace(id=2, friend_id="1234567890123456"),
            SimpleNamespace(id=3, friend_id=None),
        ]

        whitelist = self.task._collect_accept_whitelist()

        self.assertEqual({"1234567890123456": req_keep}, whitelist)

    def test_decide_reply_action_by_whitelist(self):
        req = SimpleNamespace(from_account_id=2)
        self.task._accept_whitelist = {"1234567890123456": req}

        self.assertEqual("accept", self.task._decide_reply_action("1234567890123456"))
        self.assertEqual("reject", self.task._decide_reply_action("0000000000000000"))

    def test_extract_friend_id_from_ocr(self):
        ocr_results = [
            {"text": "朋友ID", "box": (0, 0, 0, 0)},
            {"text": "2785-9199-0968-1661", "box": (0, 0, 0, 0)},
        ]
        self.assertEqual(
            "2785919909681661",
            self.task._extract_friend_id_from_ocr(ocr_results),
        )

    @patch("ptcgp_auto_v2.tasks.manage_friendship.is_text_visible")
    def test_add_sending_success_should_queue_wake_target_by_hook(
        self, is_text_visible_mock
    ):
        is_text_visible_mock.return_value = True
        req = SimpleNamespace(
            id=7,
            request_type="add",
            status="sending",
            from_account_id=1,
            to_account_id=2,
            to_friend_id="1234567890123456",
        )

        with (
            patch.object(self.task, "_save_request"),
            patch.object(self.task, "_refresh_requests"),
            patch.object(
                self.task, "_close_modal", return_value=ActionResult.ok(wait=0.1)
            ),
        ):
            result = self.task._handle_add_sending_result(req, {"ocr_results": []})

        self.assertTrue(result.success)
        self.assertIn(2, self.task._wake_account_ids)

    @patch("ptcgp_auto_v2.tasks.manage_friendship.is_text_visible")
    def test_add_sending_with_green_yes_should_complete_as_already_friend(
        self, is_text_visible_mock
    ):
        is_text_visible_mock.return_value = False
        req = SimpleNamespace(
            id=9,
            request_type="add",
            status="sending",
            from_account_id=1,
            to_account_id=2,
            to_friend_id="1234567890123456",
        )

        with (
            patch.object(
                self.task,
                "_find_green_yes_match",
                return_value=SimpleNamespace(box=(1, 2, 3, 4)),
            ),
            patch.object(
                self.task, "_complete_add_already_friend_request"
            ) as complete_mock,
            patch.object(self.task, "_refresh_requests") as refresh_mock,
            patch.object(
                self.task, "_close_modal", return_value=ActionResult.ok(wait=0.1)
            ),
        ):
            result = self.task._handle_add_sending_result(req, {"ocr_results": []})

        self.assertTrue(result.success)
        complete_mock.assert_called_once_with(req)
        refresh_mock.assert_called_once()

    @patch("ptcgp_auto_v2.tasks.manage_friendship.FriendRequestRepository")
    def test_get_pending_requests_should_sort_by_created_at(self, request_repo_cls):
        request_repo = request_repo_cls.return_value

        sending_new = SimpleNamespace(
            id=3,
            created_at=datetime(2026, 2, 10, 11, 0, 0),
            request_type="add",
            status="sending",
        )
        sended_old = SimpleNamespace(
            id=1,
            created_at=datetime(2026, 2, 10, 9, 0, 0),
            request_type="add",
            status="sended",
        )
        deleting_mid = SimpleNamespace(
            id=2,
            created_at=datetime(2026, 2, 10, 10, 0, 0),
            request_type="delete",
            status="deleting",
        )

        request_repo.get_by_from_account_and_status.return_value = [sending_new]
        request_repo.get_by_to_account_and_status.return_value = [sended_old]
        request_repo.get_by_from_account_and_type.side_effect = [[], [deleting_mid]]

        requests = self.task._get_pending_requests()

        self.assertEqual([1, 2, 3], [item.id for item in requests])

    @patch("ptcgp_auto_v2.tasks.manage_friendship.FriendshipService")
    @patch("ptcgp_auto_v2.tasks.manage_friendship.FriendRequestRepository")
    def test_on_start_should_filter_expired_add_requests(
        self,
        request_repo_cls,
        friendship_service_mock,
    ):
        """启动时应将过期 add 请求置 failed 并从待处理列表移除。"""
        request_repo = request_repo_cls.return_value
        expired_req = SimpleNamespace(
            id=1,
            request_type="add",
            status="sended",
            created_at=datetime(2026, 2, 10, 9, 0, 0),
        )
        fresh_req = SimpleNamespace(
            id=2,
            request_type="delete",
            status="deleting",
            created_at=datetime(2026, 2, 10, 10, 0, 0),
        )

        request_repo.get_by_from_account_and_status.side_effect = [[expired_req], []]
        request_repo.get_by_to_account_and_status.side_effect = [[], [], []]
        request_repo.get_external_sended_requests.side_effect = [[], []]
        request_repo.get_by_from_account_and_type.side_effect = [
            [],
            [fresh_req],
            [],
            [fresh_req],
        ]

        def _expire(req, now=None):
            return req.id == 1

        friendship_service_mock.expire_add_request_if_needed.side_effect = _expire

        self.task.on_start()

        self.assertFalse(self.task.is_completed())
        self.assertEqual([2], [item.id for item in self.task.requests_to_process])

    @patch("ptcgp_auto_v2.tasks.manage_friendship.is_text_visible")
    def test_external_sended_pending_should_defer_without_refresh_loop(
        self,
        is_text_visible_mock,
    ):
        """外部 sended 未接受时，应当本轮暂缓而不是刷新后继续同一请求。"""
        is_text_visible_mock.return_value = True
        req = SimpleNamespace(
            id=50,
            request_type="add",
            status="sended",
            to_account_id=None,
            to_friend_id="5231700486153177",
        )
        self.task.requests_to_process = [req]
        self.task.current_request = req

        with (
            patch.object(self.task, "_find_green_yes_match", return_value=None),
            patch.object(self.task, "_defer_current_request") as defer_mock,
            patch.object(
                self.task, "_close_modal", return_value=ActionResult.ok(wait=0.1)
            ),
        ):
            result = self.task._handle_external_sended_result(req, {"ocr_results": []})

        self.assertTrue(result.success)
        defer_mock.assert_called_once_with(req, "defer_external_pending")


if __name__ == "__main__":
    unittest.main()
