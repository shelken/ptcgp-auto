# -*- coding: utf-8 -*-
"""
任务运行时状态模型。

统一承载任务生命周期、页面切换与任务私有运行态。
"""

from dataclasses import dataclass, field


@dataclass
class LifecycleState:
    """任务生命周期状态。"""

    completed: bool = False
    skipped: bool = False
    failed: bool = False
    complete_reason: str | None = None
    skip_reason: str | None = None
    error: str | None = None

    def reset(self):
        """重置生命周期状态。"""
        self.completed = False
        self.skipped = False
        self.failed = False
        self.complete_reason = None
        self.skip_reason = None
        self.error = None

    def complete(self, reason: str | None = None):
        """标记任务完成。"""
        self.completed = True
        self.skipped = False
        self.failed = False
        self.complete_reason = reason
        self.skip_reason = None
        self.error = None

    def skip(self, reason: str | None = None):
        """标记任务跳过。"""
        self.completed = True
        self.skipped = True
        self.failed = False
        self.complete_reason = None
        self.skip_reason = reason
        self.error = None

    def fail(self, error: str | None = None):
        """标记任务失败。"""
        self.completed = False
        self.skipped = False
        self.failed = True
        self.complete_reason = None
        self.skip_reason = None
        self.error = error


@dataclass
class PageState:
    """页面切换与页面内动作状态。"""

    current: str | None = None
    previous: str | None = None
    action_cache: dict[str, object] = field(default_factory=dict)

    def update(self, page_name: str) -> bool:
        """更新当前页面，返回是否发生页面切换。"""
        if page_name == self.current:
            return False
        self.previous = self.current
        self.current = page_name
        return True

    def reset(self):
        """重置页面状态。"""
        self.current = None
        self.previous = None
        self.action_cache.clear()


@dataclass
class FlowState:
    """任务公共流转状态。"""

    phase: object | None = None
    status: object | None = None

    def reset(self):
        """重置流转状态。"""
        self.phase = None
        self.status = None


@dataclass
class TaskState:
    """统一任务运行时状态容器。"""

    lifecycle: LifecycleState = field(default_factory=LifecycleState)
    page: PageState = field(default_factory=PageState)
    flow: FlowState = field(default_factory=FlowState)
    data: dict[str, object] = field(default_factory=dict)

    def reset(self):
        """重置任务运行时状态。"""
        self.lifecycle.reset()
        self.page.reset()
        self.flow.reset()
        self.data.clear()
