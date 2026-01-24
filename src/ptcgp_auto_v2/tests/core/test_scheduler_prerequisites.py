import sys
import unittest
from pathlib import Path

src_dir = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(src_dir))

from ptcgp_auto_v2.core.scheduler import Scheduler
from ptcgp_auto_v2.core.task_base import TaskStatus


class FakeTaskInstance:
    def __init__(self, task_type, status, account_id, account=None):
        self.task_type = task_type
        self.status = status
        self.account_id = account_id
        self.account = account
        self.saved = False

    def save(self):
        self.saved = True


class FakeTaskRepo:
    def __init__(self, instance):
        self.instance = instance
        self.calls = []

    def get_or_create(self, account_id, task_type, reset_type):
        self.calls.append((account_id, task_type, reset_type))
        return self.instance


class FakeAccount:
    def __init__(self, account_id, friend_id=None, nickname=None, level=None):
        self.id = account_id
        self.friend_id = friend_id
        self.nickname = nickname
        self.level = level


class TestSchedulerPrerequisites(unittest.TestCase):
    def setUp(self):
        self.scheduler = Scheduler(device_addresses=[])

    def test_no_fetch_needed_returns_original_tasks(self):
        account = FakeAccount(account_id=1, friend_id="f", nickname="n", level=1)
        task = FakeTaskInstance("open_pack", TaskStatus.PENDING.value, account.id)
        prereq = FakeTaskInstance("fetch_account_info", TaskStatus.PENDING.value, account.id)
        repo = FakeTaskRepo(prereq)
        self.scheduler._task_instance_repo = repo

        result = self.scheduler._ensure_prerequisites_in_batch(account, [task])

        self.assertEqual([task], result)
        self.assertEqual([], repo.calls)

    def test_existing_fetch_task_returns_original_tasks(self):
        account = FakeAccount(account_id=1, friend_id=None, nickname=None, level=None)
        fetch_task = FakeTaskInstance("fetch_account_info", TaskStatus.PENDING.value, account.id)
        repo = FakeTaskRepo(fetch_task)
        self.scheduler._task_instance_repo = repo

        result = self.scheduler._ensure_prerequisites_in_batch(account, [fetch_task])

        self.assertEqual([fetch_task], result)
        self.assertEqual([], repo.calls)

    def test_inserts_fetch_task_and_resets_status(self):
        account = FakeAccount(account_id=1, friend_id=None, nickname=None, level=None)
        task = FakeTaskInstance("open_pack", TaskStatus.PENDING.value, account.id)
        prereq = FakeTaskInstance("fetch_account_info", TaskStatus.COMPLETED.value, account.id)
        repo = FakeTaskRepo(prereq)
        self.scheduler._task_instance_repo = repo

        result = self.scheduler._ensure_prerequisites_in_batch(account, [task])

        self.assertEqual(prereq, result[0])
        self.assertEqual(task, result[1])
        self.assertEqual(TaskStatus.PENDING.value, prereq.status)
        self.assertTrue(prereq.saved)
        self.assertTrue(repo.calls)

    def test_insert_prerequisite_blocks_original_task(self):
        account = FakeAccount(account_id=2, friend_id=None, nickname="n", level=None)
        original = FakeTaskInstance("open_pack", TaskStatus.PENDING.value, account.id, account=account)
        prereq = FakeTaskInstance("fetch_account_info", TaskStatus.COMPLETED.value, account.id)
        repo = FakeTaskRepo(prereq)
        self.scheduler._task_instance_repo = repo

        self.scheduler._insert_prerequisite_task(original, "fetch_account_info")

        self.assertEqual(TaskStatus.BLOCKED.value, original.status)
        self.assertTrue(original.saved)
        self.assertEqual(TaskStatus.PENDING.value, prereq.status)
        self.assertTrue(prereq.saved)


if __name__ == "__main__":
    unittest.main()
