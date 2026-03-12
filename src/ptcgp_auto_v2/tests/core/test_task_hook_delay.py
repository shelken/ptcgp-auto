# -*- coding: utf-8 -*-
from datetime import datetime, timedelta
from typing import Any, cast

from ptcgp_auto_v2.core.hooks import Hook, HookContext, HookResult
from ptcgp_auto_v2.core.task_base import Task


class DummyDelayHook(Hook):
    """用于测试的延时 Hook。"""

    def run(self, context: HookContext) -> tuple[HookResult, dict]:
        return HookResult.DELAY, {"delay_seconds": 60, "reason": "hook_delay"}


class DummyTask(Task):
    """用于验证 Hook delay 透传的任务。"""

    task_type = "dummy"
    pages = []

    def __init__(self):
        self.page_detector = None
        self.adb = None
        self.recognizer = None
        self._completed = True
        self.max_iterations = 1
        self.max_same_page_rounds = 1
        self._handlers = {}
        self._stop_event = None
        self._account = None
        self._hook_context = HookContext(
            device=cast(Any, object()),
            account=cast(Any, object()),
            task=self,
            executor=cast(Any, object()),
        )

    def is_completed(self) -> bool:
        return self._completed

    def handle_page(self, page_name: str, page_info: dict):
        raise AssertionError("不应进入页面处理")

    def get_post_hooks(self) -> list[Hook]:
        return [DummyDelayHook()]


def test_task_execute_should_attach_requeue_at_from_post_hook_delay():
    """后置 Hook 返回 DELAY 后，TaskResult 应包含 requeue_at。"""
    task = DummyTask()
    before = datetime.now()
    result = task.execute()
    after = datetime.now()

    assert result.success is True
    assert result.data.get("requeue_reason") == "hook_delay"
    requeue_at = result.data.get("requeue_at")
    assert isinstance(requeue_at, datetime)
    assert before + timedelta(seconds=59) <= requeue_at <= after + timedelta(seconds=61)
