# -*- coding: utf-8 -*-
"""统一状态化任务基类。"""

from collections.abc import Callable
from typing import cast

from ptcgp_auto_v2.core.task_base import Task
from ptcgp_auto_v2.core.task_state import TaskState
from ptcgp_auto_v2.utils.action_result import ActionResult

TASK_COMPLETED_KEY = "task.completed"
TASK_SKIPPED_KEY = "task.skipped"
TASK_FAILED_KEY = "task.failed"
TASK_COMPLETE_REASON_KEY = "task.complete_reason"
TASK_SKIP_REASON_KEY = "task.skip_reason"
TASK_ERROR_KEY = "task.error"
PAGE_CURRENT_KEY = "page.current"
PAGE_PREVIOUS_KEY = "page.previous"
ACTION_PREFIX = "action."


class StatefulTask(Task):
    """带统一运行时状态的任务基类。"""

    def __init__(self, adb, recognizer, page_detector):
        super().__init__(adb, recognizer, page_detector)
        self.state = TaskState()

    def state_get(self, key: str, default: object = None) -> object:
        """读取统一运行态。"""
        return self.state.get(key, default)

    def state_set(self, key: str, value: object):
        """写入统一运行态。"""
        self.state.set(key, value)

    def state_del(self, key: str, default: object = None) -> object:
        """删除单个统一运行态。"""
        return self.state.delete(key, default)

    def state_clear_prefix(self, prefix: str):
        """按前缀删除统一运行态。"""
        self.state.clear_prefix(prefix)

    def state_update(self, mapping: dict[str, object]):
        """批量写入统一运行态。"""
        self.state.update(mapping)

    def complete(self, reason: str | None = None):
        """标记任务完成。"""
        self.state_update(
            {
                TASK_COMPLETED_KEY: True,
                TASK_SKIPPED_KEY: False,
                TASK_FAILED_KEY: False,
                TASK_COMPLETE_REASON_KEY: reason,
                TASK_SKIP_REASON_KEY: None,
                TASK_ERROR_KEY: None,
            }
        )

    def skip(self, reason: str | None = None):
        """标记任务跳过。"""
        self.state_update(
            {
                TASK_COMPLETED_KEY: True,
                TASK_SKIPPED_KEY: True,
                TASK_FAILED_KEY: False,
                TASK_COMPLETE_REASON_KEY: None,
                TASK_SKIP_REASON_KEY: reason,
                TASK_ERROR_KEY: None,
            }
        )

    def fail(self, error: str | None = None):
        """标记任务失败。"""
        self.state_update(
            {
                TASK_COMPLETED_KEY: False,
                TASK_SKIPPED_KEY: False,
                TASK_FAILED_KEY: True,
                TASK_COMPLETE_REASON_KEY: None,
                TASK_SKIP_REASON_KEY: None,
                TASK_ERROR_KEY: error,
            }
        )

    def get_complete_reason(self) -> str | None:
        """获取完成原因。"""
        return cast(str | None, self.state_get(TASK_COMPLETE_REASON_KEY))

    def get_skip_reason(self) -> str | None:
        """获取跳过原因。"""
        return cast(str | None, self.state_get(TASK_SKIP_REASON_KEY))

    def get_error(self) -> str | None:
        """获取失败原因。"""
        return cast(str | None, self.state_get(TASK_ERROR_KEY))

    def is_completed(self) -> bool:
        """统一完成态判断。"""
        return bool(self.state_get(TASK_COMPLETED_KEY, False)) or self.is_failed()

    def was_skipped(self) -> bool:
        """统一跳过态判断。"""
        return bool(self.state_get(TASK_SKIPPED_KEY, False))

    def is_failed(self) -> bool:
        """统一失败态判断。"""
        return bool(self.state_get(TASK_FAILED_KEY, False))

    def is_action_done(self, key: str) -> bool:
        """检查动作是否已执行。"""
        return bool(self.state_get(f"{ACTION_PREFIX}{key}", False))

    def mark_action_done(self, key: str, value: object = True):
        """标记动作已执行。"""
        self.state_set(f"{ACTION_PREFIX}{key}", value)

    def reset_action_cache(self):
        """清空动作缓存。"""
        self.state_clear_prefix(ACTION_PREFIX)

    def get_current_page(self) -> str | None:
        """读取当前页面。"""
        return cast(str | None, self.state_get(PAGE_CURRENT_KEY))

    def get_previous_page(self) -> str | None:
        """读取上一页面。"""
        return cast(str | None, self.state_get(PAGE_PREVIOUS_KEY))

    def set_current_page(self, page_name: str) -> bool:
        """更新当前页面并返回是否发生页面切换。"""
        current_page = self.get_current_page()
        if current_page == page_name:
            return False
        self.state_set(PAGE_PREVIOUS_KEY, current_page)
        self.state_set(PAGE_CURRENT_KEY, page_name)
        return True

    def on_page_changed(
        self,
        previous_page_name: str | None,
        page_name: str,
        page_info: dict,
    ):
        """页面切换钩子，默认不做任何副作用。"""
        return None

    def on_page_updated(self, page_name: str, page_info: dict):
        """页面更新钩子，默认不做任何副作用。"""
        return None

    def handle_unmapped_page(self, page_name: str, page_info: dict) -> ActionResult:
        """处理未映射页面。"""
        return ActionResult.ok(wait=1.0)

    def handle_page(self, page_name: str, page_info: dict) -> ActionResult:
        """按页面名反射分发处理器。"""
        previous_page_name = self.get_current_page()
        if self.set_current_page(page_name):
            self.on_page_changed(previous_page_name, page_name, page_info)
        self.on_page_updated(page_name, page_info)
        handler = cast(
            Callable[[dict], ActionResult] | None,
            getattr(self, f"_handle_{page_name}", None),
        )
        if handler is not None:
            return handler(page_info)
        return self.handle_unmapped_page(page_name, page_info)
