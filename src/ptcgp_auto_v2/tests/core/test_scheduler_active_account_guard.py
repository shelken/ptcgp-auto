# -*- coding: utf-8 -*-
"""调度器账号级并发防重测试。"""

import unittest
from datetime import datetime
from types import SimpleNamespace
from unittest.mock import patch

from ptcgp_auto_v2.core.device_pool import Device
from ptcgp_auto_v2.core.scheduler import Scheduler
from ptcgp_auto_v2.core.task_status import TaskStatus


class FakeTaskInstance:
    """简化任务实例。"""

    def __init__(self, task_type: str, account_id: int):
        self.task_type = task_type
        self.account_id = account_id
        self.status = TaskStatus.PENDING.value
        self.created_at = datetime.now()
        self.saved = 0

    def save(self):
        """记录保存次数。"""
        self.saved += 1


class FakeAccount:
    """简化账号对象。"""

    def __init__(self, account_id: int, nickname: str = "acc"):
        self.id = account_id
        self.nickname = nickname
        self.task_plan_associations = []


class FakeTaskRepo:
    """简化任务仓库。"""

    def __init__(self, account_id: int, task_instances: list[FakeTaskInstance]):
        self.account_id = account_id
        self.task_instances = task_instances
        self.reset_kwargs = None

    def get_accounts_with_pending_tasks(self):
        return [self.account_id]

    def has_running_tasks(self, account_id: int):
        return False

    def get_pending_by_account(self, account_id: int):
        return list(self.task_instances)

    def get_or_create(self, account_id: int, task_type: str, reset_type: str):
        for task in self.task_instances:
            if task.account_id == account_id and task.task_type == task_type:
                return task
        raise AssertionError(f"unexpected task lookup: {account_id=} {task_type=}")

    def get_by_id(self, task_id: int):
        for task in self.task_instances:
            if getattr(task, "id", None) == task_id:
                return task
        return None

    def reset_stale_tasks(self, **kwargs):
        self.reset_kwargs = kwargs
        return 0


class FakeAccountRepo:
    """简化账号仓库。"""

    def __init__(self, account: FakeAccount):
        self.account = account

    def get_by_id(self, account_id: int):
        if self.account.id == account_id:
            return self.account
        return None


class FakeFuture:
    """可手动触发回调的 Future。"""

    def __init__(self):
        self._callbacks = []

    def add_done_callback(self, callback):
        self._callbacks.append(callback)

    def trigger_done(self):
        for callback in list(self._callbacks):
            callback(self)


class FakeExecutorPool:
    """简化线程池。"""

    def __init__(self):
        self.future = FakeFuture()
        self.submit_calls = []

    def submit(self, fn, **kwargs):
        self.submit_calls.append((fn, kwargs))
        return self.future


class TestSchedulerActiveAccountGuard(unittest.TestCase):
    """验证账号级并发防重行为。"""

    def test_should_skip_account_when_it_is_marked_active(self):
        """账号处于活动集合时，不应再次被批量调度。"""
        scheduler = Scheduler(device_addresses=[])
        task = FakeTaskInstance("claim_rewards", 1)
        account = FakeAccount(account_id=1)
        scheduler._task_instance_repo = FakeTaskRepo(1, [task])
        scheduler._account_repo = FakeAccountRepo(account)
        scheduler._ensure_prerequisites_in_batch = lambda a, t: t
        scheduler._order_tasks_by_plan = lambda a, t: t
        scheduler._active_account_ids = {1}

        result = scheduler._get_next_account_batch()

        self.assertIsNone(result)

    def test_stale_reset_should_exclude_active_accounts(self):
        """异常任务重置时应排除活动账号，避免误回收。"""
        scheduler = Scheduler(device_addresses=[])
        repo = FakeTaskRepo(1, [])
        scheduler._task_instance_repo = repo
        scheduler._active_account_ids = {1, 2}

        scheduler._check_and_reset_stale_tasks()

        self.assertIsNotNone(repo.reset_kwargs)
        self.assertIn("exclude_account_ids", repo.reset_kwargs)
        self.assertEqual([1, 2], sorted(repo.reset_kwargs["exclude_account_ids"]))

    def test_submit_batch_should_register_and_release_active_account(self):
        """提交批量任务时应注册活动账号，任务结束后释放。"""
        scheduler = Scheduler(device_addresses=[])
        scheduler._executor_pool = FakeExecutorPool()
        scheduler._active_account_ids = set()

        task = FakeTaskInstance("claim_rewards", 7)
        account = FakeAccount(account_id=7, nickname="skn7")
        device = Device(address="127.0.0.1:5555")

        scheduler._submit_account_executor(device, account, [task])

        self.assertIn(7, scheduler._active_account_ids)
        self.assertEqual(TaskStatus.RUNNING.value, task.status)
        self.assertEqual(1, task.saved)

        scheduler._executor_pool.future.trigger_done()
        self.assertNotIn(7, scheduler._active_account_ids)

    def test_run_single_task_marks_tasks_running_before_executor(self):
        """单任务调试路径在进入执行器前也应先标记任务 running。"""
        scheduler = Scheduler(device_addresses=[])
        task = FakeTaskInstance("claim_rewards", 7)
        task.id = 1
        account = FakeAccount(account_id=7, nickname="skn7")
        repo = FakeTaskRepo(7, [task])

        scheduler._init_repositories = lambda: None
        scheduler._task_instance_repo = repo
        scheduler._account_repo = FakeAccountRepo(account)
        scheduler._ensure_prerequisites_in_batch = lambda a, t: t

        def fake_run(executor_self):
            self.assertEqual(
                [TaskStatus.RUNNING.value],
                [t.status for t in executor_self.task_instances],
            )
            self.assertEqual([1], [t.saved for t in executor_self.task_instances])
            for task_instance in executor_self.task_instances:
                task_instance.status = TaskStatus.COMPLETED.value

        fake_task_class = SimpleNamespace(
            reset_type=SimpleNamespace(value="daily")
        )
        with patch(
            "ptcgp_auto_v2.core.executor.AccountExecutor.run",
            fake_run,
        ), patch(
            "ptcgp_auto_v2.core.scheduler.TaskRegistry.get",
            return_value=fake_task_class,
        ):
            success = scheduler.run_single_task(
                device_address="127.0.0.1:5555",
                account_id=7,
                task_type="claim_rewards",
            )

        self.assertTrue(success)


if __name__ == "__main__":
    unittest.main()
