import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

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


if __name__ == "__main__":
    unittest.main()
