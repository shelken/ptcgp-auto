import sys
import unittest
from datetime import datetime
from pathlib import Path

src_dir = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(src_dir))

from ptcgp_auto_v2.core.executor import BaseExecutor
from ptcgp_auto_v2.core.task_status import TaskStatus


class FakeTaskInstance:
    def __init__(self):
        self.status = None
        self.last_completed_at = None
        self.error_message = "previous"
        self.updated_at = None
        self.saved = False

    def save(self):
        self.saved = True


class FakeDevice:
    def __init__(self):
        self.address = "device"

    def update_current_account(self, account_id):
        return None


class FakeDevicePool:
    def release(self, device):
        return None


class DummyExecutor(BaseExecutor):
    def __init__(self):
        super().__init__(FakeDevice(), FakeDevicePool())
        self.unblocked = False

    def _unblock_dependent_tasks(self, account):
        self.unblocked = True

    def run(self):
        return None


class TestApplyTaskStatus(unittest.TestCase):
    def setUp(self):
        self.executor = DummyExecutor()
        self.account = object()

    def test_completed_status_sets_timestamp_and_unblocks(self):
        task = FakeTaskInstance()
        self.executor._apply_task_status(
            task_instance=task,
            account=self.account,
            status=TaskStatus.COMPLETED,
            clear_error_on_success=True,
        )

        self.assertEqual(TaskStatus.COMPLETED.value, task.status)
        self.assertIsInstance(task.last_completed_at, datetime)
        self.assertIsNone(task.error_message)
        self.assertIsInstance(task.updated_at, datetime)
        self.assertTrue(task.saved)
        self.assertTrue(self.executor.unblocked)

    def test_completed_status_keeps_existing_error_when_not_cleared(self):
        task = FakeTaskInstance()
        self.executor._apply_task_status(
            task_instance=task,
            account=self.account,
            status=TaskStatus.COMPLETED,
            clear_error_on_success=False,
        )

        self.assertEqual("previous", task.error_message)

    def test_failed_status_sets_error(self):
        task = FakeTaskInstance()
        self.executor._apply_task_status(
            task_instance=task,
            account=self.account,
            status=TaskStatus.FAILED,
            error_message="failed",
        )

        self.assertEqual(TaskStatus.FAILED.value, task.status)
        self.assertEqual("failed", task.error_message)
        self.assertIsInstance(task.updated_at, datetime)
        self.assertTrue(task.saved)


if __name__ == "__main__":
    unittest.main()
