# -*- coding: utf-8 -*-
"""
统一状态化任务基类。

提供统一的生命周期状态、页面切换跟踪与反射式页面分发。
"""

from collections.abc import Callable
from typing import cast

from ptcgp_auto_v2.core.task_base import Task
from ptcgp_auto_v2.core.task_state import TaskState
from ptcgp_auto_v2.utils.action_result import ActionResult


class StatefulTask(Task):
    """带统一运行时状态的任务基类。"""

    def __init__(self, adb, recognizer, page_detector):
        super().__init__(adb, recognizer, page_detector)
        self.state = TaskState()

    def complete(self, reason: str | None = None):
        """标记任务完成。"""
        self.state.lifecycle.complete(reason)

    def skip(self, reason: str | None = None):
        """标记任务跳过。"""
        self.state.lifecycle.skip(reason)

    def fail(self, error: str | None = None):
        """标记任务失败。"""
        self.state.lifecycle.fail(error)

    def get_complete_reason(self) -> str | None:
        """获取完成原因。"""
        return self.state.lifecycle.complete_reason

    def get_skip_reason(self) -> str | None:
        """获取跳过原因。"""
        return self.state.lifecycle.skip_reason

    def get_error(self) -> str | None:
        """获取失败原因。"""
        return self.state.lifecycle.error

    def is_completed(self) -> bool:
        """统一完成态判断。"""
        return self.state.lifecycle.completed or self.state.lifecycle.failed

    def was_skipped(self) -> bool:
        """统一跳过态判断。"""
        return self.state.lifecycle.skipped

    def is_failed(self) -> bool:
        """统一失败态判断。"""
        return self.state.lifecycle.failed

    def is_action_done(self, key: str) -> bool:
        """检查页面内动作是否已执行。"""
        return bool(self.state.page.action_cache.get(key, False))

    def mark_action_done(self, key: str, value: object = True):
        """标记页面内动作已执行。"""
        self.state.page.action_cache[key] = value

    def reset_action_cache(self):
        """重置页面内动作缓存。"""
        self.state.page.action_cache.clear()

    @property
    def current_page(self) -> str | None:
        """当前页面名。"""
        return self.state.page.current

    @property
    def previous_page(self) -> str | None:
        """上一页面名。"""
        return self.state.page.previous

    def on_page_changed(
        self,
        previous_page_name: str | None,
        page_name: str,
        page_info: dict,
    ):
        """页面切换钩子，默认不做任何副作用。"""
        return None

    def on_page_updated(self, page_name: str, page_info: dict):
        """页面更新钩子（包括首次进入与同页重复识别），默认不做任何副作用。"""
        return None

    def handle_unmapped_page(self, page_name: str, page_info: dict) -> ActionResult:
        """处理未映射页面。"""
        return ActionResult.ok(wait=1.0)

    def handle_page(self, page_name: str, page_info: dict) -> ActionResult:
        """按页面名反射分发处理器。"""
        previous_page_name = self.state.page.current
        if self.state.page.update(page_name):
            self.on_page_changed(previous_page_name, page_name, page_info)
        self.on_page_updated(page_name, page_info)
        handler = cast(
            Callable[[dict], ActionResult] | None,
            getattr(self, f"_handle_{page_name}", None),
        )
        if handler is not None:
            return handler(page_info)
        return self.handle_unmapped_page(page_name, page_info)
