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
        self.task_type = "open_pack"
        self.reset_type = "daily"
        self.status = None
        self.last_completed_at = None
        self.schedule_anchor_at = None
        self.last_duration_seconds = None
        self.next_run_at = None
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
        self.account = type("FakeAccount", (), {"task_plan_associations": []})()

    def test_completed_status_sets_timestamp_and_unblocks(self):
        task = FakeTaskInstance()
        self.executor._apply_task_status(
            task_instance=task,
            account=self.account,
            status=TaskStatus.COMPLETED,
            clear_error_on_success=True,
            duration_seconds=125,
        )

        self.assertEqual(TaskStatus.COMPLETED.value, task.status)
        self.assertIsInstance(task.last_completed_at, datetime)
        self.assertIsInstance(task.schedule_anchor_at, datetime)
        self.assertEqual(125, task.last_duration_seconds)
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
            duration_seconds=8,
        )

        self.assertEqual("previous", task.error_message)
        self.assertEqual(8, task.last_duration_seconds)

    def test_completed_status_can_preserve_last_completed_at(self):
        task = FakeTaskInstance()
        previous_completed_at = datetime(2026, 3, 1, 8, 30, 0)
        task.last_completed_at = previous_completed_at

        self.executor._apply_task_status(
            task_instance=task,
            account=self.account,
            status=TaskStatus.COMPLETED,
            clear_error_on_success=True,
            duration_seconds=12,
            preserve_last_completed_at=True,
        )

        self.assertEqual(previous_completed_at, task.last_completed_at)
        self.assertIsInstance(task.schedule_anchor_at, datetime)
        self.assertIsInstance(task.next_run_at, datetime)
        self.assertEqual(12, task.last_duration_seconds)
        self.assertTrue(self.executor.unblocked)

    def test_failed_status_sets_error(self):
        task = FakeTaskInstance()
        self.executor._apply_task_status(
            task_instance=task,
            account=self.account,
            status=TaskStatus.FAILED,
            error_message="failed",
            duration_seconds=0,
        )

        self.assertEqual(TaskStatus.FAILED.value, task.status)
        self.assertEqual("failed", task.error_message)
        self.assertEqual(0, task.last_duration_seconds)
        self.assertIsInstance(task.updated_at, datetime)
        self.assertTrue(task.saved)

    def test_running_status_does_not_override_last_duration(self):
        task = FakeTaskInstance()
        task.last_duration_seconds = 33

        self.executor._apply_task_status(
            task_instance=task,
            account=self.account,
            status=TaskStatus.RUNNING,
            duration_seconds=120,
        )

        self.assertEqual(TaskStatus.RUNNING.value, task.status)
        self.assertEqual(33, task.last_duration_seconds)


if __name__ == "__main__":
    unittest.main()
