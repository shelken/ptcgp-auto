import sys
import unittest
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


if __name__ == "__main__":
    unittest.main()
