import sys
import unittest
from datetime import datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

src_dir = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(src_dir))

from ptcgp_auto_v2.services.friendship_service import FriendshipService


class TestFriendshipService(unittest.TestCase):
    @patch("ptcgp_auto_v2.services.friendship_service.TaskInstanceRepository")
    def test_ensure_manage_friendship_pending_create_when_missing(self, task_repo_cls):
        repo = task_repo_cls.return_value
        repo.get_by_account_and_type.return_value = None
        repo.get_or_create.return_value = SimpleNamespace(
            status="completed", save=lambda: None
        )

        ok = FriendshipService.ensure_manage_friendship_pending(account_id=66)

        self.assertTrue(ok)
        repo.get_or_create.assert_called_once_with(
            account_id=66,
            task_type="manage_friendship",
            reset_type="once",
        )

    @patch("ptcgp_auto_v2.services.friendship_service.FriendRequestRepository")
    def test_expire_add_request_if_needed_should_mark_external_as_failed(
        self, repo_cls
    ):
        """外部 add 请求超过 10 分钟应标记失败。"""
        repo = repo_cls.return_value
        request = SimpleNamespace(
            request_type="add",
            status="sended",
            to_account_id=None,
            created_at=datetime.now() - timedelta(minutes=11),
            failed_reason=None,
            updated_at=None,
        )

        changed = FriendshipService.expire_add_request_if_needed(request)

        self.assertTrue(changed)
        self.assertEqual("failed", request.status)
        repo.update.assert_called_once_with(request)

    @patch("ptcgp_auto_v2.services.friendship_service.FriendRequestRepository")
    def test_expire_add_request_if_needed_should_mark_internal_as_failed(
        self, repo_cls
    ):
        """系统内 add 请求超过 30 分钟应标记失败。"""
        repo = repo_cls.return_value
        request = SimpleNamespace(
            request_type="add",
            status="sending",
            to_account_id=2,
            created_at=datetime.now() - timedelta(minutes=31),
            failed_reason=None,
            updated_at=None,
        )

        changed = FriendshipService.expire_add_request_if_needed(request)

        self.assertTrue(changed)
        self.assertEqual("failed", request.status)
        repo.update.assert_called_once_with(request)


if __name__ == "__main__":
    unittest.main()
