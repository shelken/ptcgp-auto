# -*- coding: utf-8 -*-
"""任务同页停滞恢复测试。"""

from ptcgp_auto_v2.core.task_base import ActionResult, ResetType, Task


class _PageDetector:
    def __init__(self):
        self.calls = 0

    def detect(self, **kwargs):
        self.calls += 1
        if self.calls <= 2:
            return "stuck_page", {}
        return "done_page", {}


class _RecoveringTask(Task):
    task_type = "recovering_task"
    reset_type = ResetType.ONCE
    max_iterations = 4
    max_same_page_rounds = 2

    def __init__(self):
        super().__init__(adb=object(), recognizer=None, page_detector=_PageDetector())
        self.completed = False
        self.recoveries = 0

    def is_completed(self):
        return self.completed

    def handle_page(self, page_name: str, page_info: dict) -> ActionResult:
        if page_name == "done_page":
            self.completed = True
        return ActionResult.ok(wait=0)

    def handle_same_page_stuck(
        self,
        page_name: str,
        page_info: dict,
        same_page_count: int,
    ) -> ActionResult | None:
        self.recoveries += 1
        return ActionResult.ok(wait=0)


def test_task_can_recover_once_before_same_page_failure():
    """任务可在同页停滞阈值处恢复，并继续完成当前执行。"""
    task = _RecoveringTask()

    result = task.execute()

    assert result.success is True
    assert task.recoveries == 1
    assert task.page_detector.calls == 3
