# -*- coding: utf-8 -*-
"""执行器耗时记录测试。"""

from types import SimpleNamespace

from ptcgp_auto_v2.core.executor import AccountExecutor, BaseExecutor
from ptcgp_auto_v2.core.task_base import TaskResult
from ptcgp_auto_v2.core.task_status import TaskStatus


class FakeTaskInstance:
    """最小任务实例替身。"""

    def __init__(self, task_type: str, account, task_id: int = 1):
        self.id = task_id
        self.account_id = account.id
        self.account = account
        self.task_type = task_type
        self.status = "pending"
        self.reset_type = "daily"
        self.error_message = None
        self.last_completed_at = None
        self.last_duration_seconds = None
        self.next_run_at = None
        self.updated_at = None
        self.saved = False

    def save(self):
        self.saved = True


class FakeDevice:
    """最小设备替身。"""

    def __init__(self):
        self.address = "device:5555"

    def update_current_account(self, _account_id):
        return None


class FakeDevicePool:
    """最小设备池替身。"""

    def release(self, _device):
        return None


class FakeTask:
    """可配置执行结果的任务替身。"""

    def __init__(self, expected_skip_pre_hooks: bool, result: TaskResult):
        self.expected_skip_pre_hooks = expected_skip_pre_hooks
        self.result = result

    def execute(self, skip_pre_hooks: bool = False) -> TaskResult:
        assert skip_pre_hooks is self.expected_skip_pre_hooks
        return self.result


class DurationExecutor(BaseExecutor):
    """用于验证前置任务耗时隔离的执行器。"""

    def __init__(self, account, task_map: dict[str, list[FakeTask]], prereq_instances):
        super().__init__(FakeDevice(), FakeDevicePool())
        self.account = account
        self.task_map = task_map
        self.prereq_instances = prereq_instances

    def _build_task(self, task_instance, account):
        return self.task_map[task_instance.task_type].pop(0)

    def _get_or_create_task_instance(self, account_id: int, task_type: str):
        assert account_id == self.account.id
        return self.prereq_instances[task_type]

    def _notify_task_status(self, task_instance, status: str, message: str):
        return None

    def run(self):
        return None


def test_execute_task_with_prerequisites_keeps_main_duration_isolated(monkeypatch):
    """主任务耗时不应混入前置任务耗时。"""
    account = SimpleNamespace(
        id=1,
        nickname="main",
        task_plan_associations=[],
    )
    main_instance = FakeTaskInstance("main_task", account, task_id=1)
    prereq_instance = FakeTaskInstance("pre_task", account, task_id=2)

    executor = DurationExecutor(
        account=account,
        task_map={
            "main_task": [
                FakeTask(
                    expected_skip_pre_hooks=False,
                    result=TaskResult.skip("等待前置任务", pre_task_types=["pre_task"]),
                ),
                FakeTask(
                    expected_skip_pre_hooks=True,
                    result=TaskResult.ok(complete_reason="done"),
                ),
            ],
            "pre_task": [
                FakeTask(
                    expected_skip_pre_hooks=False,
                    result=TaskResult.ok(complete_reason="pre-done"),
                )
            ],
        },
        prereq_instances={"pre_task": prereq_instance},
    )

    monotonic_values = iter([0.0, 1.2, 10.0, 12.4, 20.0, 21.6])
    monkeypatch.setattr(
        "ptcgp_auto_v2.core.executor.time.monotonic",
        lambda: next(monotonic_values),
    )

    result = executor._execute_task_with_prerequisites(main_instance, account)

    assert result.success is True
    assert executor._get_result_duration_seconds(result) == 3
    assert prereq_instance.status == TaskStatus.COMPLETED.value
    assert prereq_instance.last_duration_seconds == 2


def test_account_executor_single_task_switch_failure_records_zero_duration(monkeypatch):
    """统一执行器在单任务切换失败时应写入 0 秒耗时。"""
    account = SimpleNamespace(
        id=1,
        nickname="user",
        display_name="user",
        task_plan_associations=[],
    )
    task_instance = FakeTaskInstance("open_pack", account, task_id=1)
    executor = AccountExecutor(
        FakeDevice(),
        account,
        [task_instance],
        FakeDevicePool(),
    )

    monkeypatch.setattr(executor, "_init_components", lambda: None)
    monkeypatch.setattr(executor, "_is_current_account", lambda _account: False)
    monkeypatch.setattr(executor, "_switch_account", lambda _account: False)
    monkeypatch.setattr(executor, "_cleanup", lambda: None)
    monkeypatch.setattr(executor, "_notify_task_status", lambda *_args, **_kwargs: None)

    executor.run()

    assert task_instance.status == TaskStatus.FAILED.value
    assert task_instance.error_message == "账号切换失败"
    assert task_instance.last_duration_seconds == 0


def test_account_executor_multi_task_switch_failure_records_zero_duration(
    monkeypatch,
):
    """统一执行器账号切换失败时应为所有任务写入 0 秒耗时。"""
    account = SimpleNamespace(
        id=1,
        nickname="batch",
        display_name="batch",
        task_plan_associations=[],
    )
    task_instances = [
        FakeTaskInstance("open_pack", account, task_id=1),
        FakeTaskInstance("claim_gifts", account, task_id=2),
    ]
    executor = AccountExecutor(
        FakeDevice(),
        account,
        task_instances,
        FakeDevicePool(),
    )

    monkeypatch.setattr(executor, "_init_components", lambda: None)
    monkeypatch.setattr(executor, "_is_current_account", lambda _account: False)
    monkeypatch.setattr(executor, "_switch_account", lambda _account: False)
    monkeypatch.setattr(executor, "_cleanup", lambda: None)
    monkeypatch.setattr(executor, "_notify_task_status", lambda *_args, **_kwargs: None)

    executor.run()

    assert [task.status for task in task_instances] == [
        TaskStatus.FAILED.value,
        TaskStatus.FAILED.value,
    ]
    assert [task.last_duration_seconds for task in task_instances] == [0, 0]


def test_account_executor_catches_non_runtime_error(monkeypatch):
    """统一执行器应收口非 RuntimeError，避免 Future 冒泡未处理异常。"""
    account = SimpleNamespace(
        id=1,
        nickname="batch",
        display_name="batch",
        task_plan_associations=[],
    )
    task_instances = [FakeTaskInstance("claim_rewards", account, task_id=1)]
    executor = AccountExecutor(
        FakeDevice(),
        account,
        task_instances,
        FakeDevicePool(),
    )

    monkeypatch.setattr(executor, "_prepare_run", lambda: True)
    monkeypatch.setattr(
        executor,
        "_execute_task_with_prerequisites",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            KeyError("CGImageSourceCreateWithData")
        ),
    )
    monkeypatch.setattr(executor, "_cleanup", lambda: None)
    monkeypatch.setattr(executor, "_notify_task_status", lambda *_args, **_kwargs: None)

    executor.run()

    assert task_instances[0].status == TaskStatus.FAILED.value
    assert task_instances[0].error_message == "'CGImageSourceCreateWithData'"
    assert task_instances[0].last_duration_seconds == 0
