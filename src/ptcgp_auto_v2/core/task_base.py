# -*- coding: utf-8 -*-
"""
任务基类与注册表模块

定义可插拔任务的接口规范和注册机制。
"""

import logging
import threading
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import TYPE_CHECKING, Any, Callable, Optional

from ptcgp_auto_v2.infra.adb import AdbController
from ptcgp_auto_v2.infra.ocr import OcrEngine
from ptcgp_auto_v2.infra.page_detector import PageDetector
from ptcgp_auto_v2.infra.template import TemplateMatcher
from ptcgp_auto_v2.utils.action_result import ActionResult

if TYPE_CHECKING:
    from ptcgp_auto_v2.core.hooks import Hook, HookContext
    from ptcgp_auto_v2.db.models import Account


Recognizer = tuple[OcrEngine, TemplateMatcher]
"""识别器类型（OCR + 模板匹配器）。"""


logger = logging.getLogger(__name__)


class ResetType(Enum):
    """任务重置类型"""

    DAILY = "daily"  # 每日重置
    WEEKLY = "weekly"  # 每周重置
    ONCE = "once"  # 一次性任务
    INTERVAL = "interval"  # 按时间间隔重置（需要配置 interval_seconds）


MAX_TASK_ITERATIONS = 100  # 最大执行迭代次数
MAX_UNKNOWN_PAGES = 30  # 连续未知页面上限


@dataclass
class TaskResult:
    """
    任务执行结果

    用于 execute 方法返回最终状态。
    """

    success: bool
    skipped: bool = False  # 是否被跳过（不更新 last_completed_at）
    preserve_last_completed_at: bool = False  # 是否保留上次完成时间
    skip_reason: Optional[str] = None  # 跳过原因
    error: Optional[str] = None
    data: dict = field(default_factory=dict)  # 附加数据

    @classmethod
    def ok(cls, **data) -> "TaskResult":
        """创建成功结果"""
        return cls(success=True, data=data)

    @classmethod
    def ok_without_timestamp(cls, **data) -> "TaskResult":
        """创建成功结果，但不更新 last_completed_at。"""
        return cls(success=True, preserve_last_completed_at=True, data=data)

    @classmethod
    def fail(cls, error: str, **data) -> "TaskResult":
        """创建失败结果"""
        return cls(success=False, error=error, data=data)

    @classmethod
    def skip(cls, reason: str, **data) -> "TaskResult":
        """创建跳过结果（不更新 last_completed_at）"""
        return cls(success=True, skipped=True, skip_reason=reason, data=data)


class Task(ABC):
    """
    任务基类

    所有可插拔任务必须继承此类并实现抽象方法。
    任务采用「目标驱动 + 页面响应」的执行模式：
    - 目标驱动：任务知道自己的完成条件
    - 页面响应：根据当前页面执行相应动作
    """

    # 任务类型标识（子类必须覆盖）
    task_type: str = ""

    # 任务重置类型
    reset_type: ResetType = ResetType.DAILY

    # 任务专用页面规则（会与公共规则合并）
    pages: list[dict] = []

    # 最大执行迭代次数
    max_iterations: int = MAX_TASK_ITERATIONS

    # 连续未知页面上限
    max_unknown_pages: int = MAX_UNKNOWN_PAGES

    # 页面检测默认截图模式：False=默认链路，True=无损截图
    # 当 部分页面文本识别不够好且无法调整 或 需要高精度文本时 设为 True
    screenshot_lossless: bool = False

    def __init__(
        self,
        adb: AdbController,
        recognizer: Optional[Recognizer],
        page_detector: PageDetector,
    ):
        """
        初始化任务

        Args:
            adb: ADB 控制器实例
            recognizer: 识别器实例
            page_detector: 页面检测器实例
        """
        self.adb = adb
        self.recognizer: Optional[Recognizer] = recognizer
        self.page_detector = page_detector
        self._account: Optional["Account"] = None
        self._handlers: dict[str, Callable[[dict], ActionResult]] = {}
        self._stop_event: Optional[threading.Event] = None
        self._hook_context: Optional["HookContext"] = None
        self._preserve_last_completed_at = False

    def set_stop_event(self, stop_event: threading.Event):
        """设置停止事件，用于响应外部中断信号"""
        self._stop_event = stop_event

    def _should_stop(self) -> bool:
        """检查是否应该停止执行"""
        if self._stop_event and self._stop_event.is_set():
            return True
        return False

    def register_handlers(self, mapping: dict[str, Callable[[dict], ActionResult]]):
        """注册页面处理器映射（后注册覆盖同名）"""
        if not mapping:
            return
        self._handlers.update(mapping)

    @property
    def account(self) -> "Account":
        """当前执行的账号"""
        if self._account is None:
            raise RuntimeError("任务未绑定账号")
        return self._account

    def bind_account(self, account: "Account"):
        """绑定执行账号"""
        self._account = account

    def set_hook_context(self, context: "HookContext"):
        """设置 Hook 上下文（由执行器注入）"""
        self._hook_context = context

    @abstractmethod
    def is_completed(self) -> bool:
        """
        判断任务是否已完成（目标状态）

        Returns:
            True 表示任务已完成，False 表示需要继续执行
        """
        pass

    @abstractmethod
    def handle_page(self, page_name: str, page_info: dict) -> ActionResult:
        """
        处理识别到的页面（页面响应）

        Args:
            page_name: 识别到的页面名称
            page_info: 页面信息（包含匹配的模板、文字等）

        Returns:
            ActionResult 表示本次动作的执行结果
        """
        pass

    def on_start(self):
        """
        任务开始前的钩子方法

        子类可覆盖此方法进行初始化操作。
        """
        pass

    def mark_completed_without_timestamp(self, reason: Optional[str] = None):
        """标记本次完成需要保留上次完成时间。"""
        self._preserve_last_completed_at = True
        if reason is not None:
            setattr(self, "_complete_reason", reason)

    def should_preserve_last_completed_at(self) -> bool:
        """是否保留上次完成时间。"""
        return self._preserve_last_completed_at

    def on_complete(self, result: TaskResult):
        """
        任务完成后的钩子方法

        Args:
            result: 任务执行结果
        """
        pass

    def get_pre_hooks(self) -> list["Hook"]:
        """动态获取前置 Hook（可基于任务/账号状态生成）"""
        return []

    def get_post_hooks(self) -> list["Hook"]:
        """动态获取后置 Hook（可基于任务/账号状态生成）"""
        return []

    def _run_pre_hooks(self) -> Optional[TaskResult]:
        """执行前置 Hook，收集并返回前置任务列表。"""
        from ptcgp_auto_v2.core.hooks import HookResult

        pre_hooks = self.get_pre_hooks()
        if not pre_hooks:
            return None

        if self._hook_context is None:
            return TaskResult.fail("Hook 上下文未初始化")

        pre_task_types: list[str] = []
        for hook in pre_hooks:
            result, data = hook.run(self._hook_context)
            if result == HookResult.ABORT:
                error_msg = data.get("error", "PreHook aborted")
                return TaskResult.fail(error_msg)
            if result == HookResult.SKIP:
                reason = data.get("reason", "前置条件不满足")
                return TaskResult.skip(reason=reason)
            if result == HookResult.INSERT_TASK:
                task_type = data.get("task_type")
                if (
                    isinstance(task_type, str)
                    and task_type
                    and task_type not in pre_task_types
                ):
                    pre_task_types.append(task_type)
            if result == HookResult.DELAY:
                requeue_at = self._extract_requeue_time(data)
                if requeue_at is not None:
                    return TaskResult.ok(
                        requeue_at=requeue_at,
                        requeue_reason=data.get("reason", "前置 Hook 延时"),
                    )
                return TaskResult.fail("前置 Hook 延时参数无效")

        if pre_task_types:
            return TaskResult.skip(
                reason="等待前置任务",
                pre_task_types=pre_task_types,
                pre_task_type=pre_task_types[0],
            )

        return None

    def _extract_requeue_time(self, data: dict) -> Optional[datetime]:
        """从 Hook 数据提取下次执行时间。"""
        run_at = data.get("run_at")
        if isinstance(run_at, datetime):
            return run_at

        delay_seconds = data.get("delay_seconds")
        if isinstance(delay_seconds, (int, float)) and delay_seconds >= 0:
            return datetime.now() + timedelta(seconds=float(delay_seconds))
        return None

    def _run_post_hooks(self) -> dict:
        """执行后置 Hook（无论主任务成功失败），返回附加结果。"""
        from ptcgp_auto_v2.core.hooks import HookResult

        post_hooks = self.get_post_hooks()
        if not post_hooks:
            return {}
        if self._hook_context is None:
            return {}

        post_data: dict = {}
        for hook in post_hooks:
            result, data = hook.run(self._hook_context)
            if result == HookResult.DELAY:
                requeue_at = self._extract_requeue_time(data)
                if requeue_at is not None:
                    post_data["requeue_at"] = requeue_at
                    post_data["requeue_reason"] = data.get("reason", "后置 Hook 延时")
        return post_data

    def handle_unknown_page(self, page_info) -> ActionResult:
        """
        处理未知页面的钩子方法

        当页面检测器无法识别当前页面时调用。
        子类可覆盖此方法实现自定义兜底逻辑（如点击屏幕中心）。

        Returns:
            ActionResult 表示处理结果，默认等待 1 秒后重新识别
        """
        return ActionResult.wait(1.0)

    def execute(self, skip_pre_hooks: bool = False) -> TaskResult:
        """
        执行任务的主循环

        采用目标驱动 + 页面响应的混合模式：
        1. 检查是否已达到目标状态
        2. 识别当前页面
        3. 执行页面对应的动作
        4. 循环直到完成或超时

        Returns:
            TaskResult 表示任务执行结果
        """
        import time

        self._preserve_last_completed_at = False
        self.on_start()
        if not skip_pre_hooks:
            pre_result = self._run_pre_hooks()
            if pre_result:
                self._log_task_iterations(pre_result)
                self.on_complete(pre_result)
                return pre_result

        unknown_count = 0
        result: Optional[TaskResult] = None

        for iteration in range(self.max_iterations):
            # 检查停止信号
            if self._should_stop():
                result = TaskResult.fail("收到停止信号", iterations=iteration)
                break

            # 检查目标状态
            if self.is_completed():
                # 检查是否是跳过的情况
                was_skipped = getattr(self, "was_skipped", None)  # type: ignore[attr-defined]
                if callable(was_skipped) and was_skipped():
                    skip_reason = getattr(self, "_skip_reason", None)
                    result = TaskResult.skip(
                        reason=skip_reason or "未知原因", iterations=iteration
                    )
                else:
                    complete_reason = getattr(self, "_complete_reason", None)
                    preserve_last_completed_at = (
                        self.should_preserve_last_completed_at()
                    )
                    if complete_reason:
                        if preserve_last_completed_at:
                            result = TaskResult.ok_without_timestamp(
                                iterations=iteration,
                                complete_reason=complete_reason,
                            )
                        else:
                            result = TaskResult.ok(
                                iterations=iteration,
                                complete_reason=complete_reason,
                            )
                    else:
                        if preserve_last_completed_at:
                            result = TaskResult.ok_without_timestamp(
                                iterations=iteration
                            )
                        else:
                            result = TaskResult.ok(iterations=iteration)
                break

            # 识别当前页面
            page_name, page_info = self.page_detector.detect(
                lossless=self.screenshot_lossless
            )

            # 处理未知页面
            if page_name == "unknown":
                unknown_count += 1
                if unknown_count >= self.max_unknown_pages:
                    result = TaskResult.fail(
                        f"连续 {self.max_unknown_pages} 次未识别页面",
                        iterations=iteration,
                    )
                    break
                # 调用未知页面处理器（子类可覆盖）
                action_result = self.handle_unknown_page(page_info)
                if not action_result.success:
                    result = TaskResult.fail(
                        action_result.error or "未知页面处理失败",
                        iterations=iteration,
                    )
                    break
                time.sleep(action_result.should_wait)
                continue

            # 重置未知计数
            unknown_count = 0

            handler = self._handlers.get(page_name)
            if handler:
                action_result = handler(page_info)
            else:
                action_result = self.handle_page(page_name, page_info)

            if not action_result.success:
                result = TaskResult.fail(
                    action_result.error or "动作执行失败",
                    iterations=iteration,
                    last_page=page_name,
                )
                break

            # 等待
            time.sleep(action_result.should_wait)

        # 超过最大迭代次数
        if result is None:
            result = TaskResult.fail(
                f"超过最大迭代次数 {self.max_iterations}",
                iterations=self.max_iterations,
            )

        post_data = self._run_post_hooks()
        if result.success and not result.skipped and post_data:
            result.data.update(post_data)
        self._log_task_iterations(result)
        self.on_complete(result)
        return result

    def _log_task_iterations(self, result: TaskResult):
        """打印任务结束时的实际迭代次数。"""
        iterations = result.data.get("iterations")
        actual_iterations = 0
        if isinstance(iterations, int) and iterations >= 0:
            if iterations >= self.max_iterations:
                actual_iterations = self.max_iterations
            else:
                actual_iterations = iterations + 1

        if result.skipped:
            status_text = "skipped"
        elif result.success:
            status_text = "success"
        else:
            status_text = "failed"

        logger.info(
            "任务结束: %s, status=%s, 实际迭代次数=%s",
            self.task_type,
            status_text,
            actual_iterations,
        )


class TaskRegistry:
    """
    任务注册表

    管理所有可用的任务类型，支持通过装饰器注册。
    """

    _tasks: dict[str, type[Task]] = {}

    @classmethod
    def register(cls, task_type: str) -> Callable[[type[Task]], type[Task]]:
        """
        注册任务类的装饰器

        用法:
            @TaskRegistry.register("open_pack")
            class OpenPackTask(Task):
                ...

        Args:
            task_type: 任务类型标识

        Returns:
            装饰器函数
        """

        def decorator(task_class: type[Task]) -> type[Task]:
            if task_type in cls._tasks:
                raise ValueError(f"任务类型 '{task_type}' 已被注册")
            task_class.task_type = task_type
            cls._tasks[task_type] = task_class
            return task_class

        return decorator

    @classmethod
    def get(cls, task_type: str) -> type[Task]:
        """
        获取任务类

        Args:
            task_type: 任务类型标识

        Returns:
            任务类

        Raises:
            ValueError: 未知的任务类型
        """
        if task_type not in cls._tasks:
            raise ValueError(f"未知的任务类型: {task_type}")
        return cls._tasks[task_type]

    @classmethod
    def get_or_none(cls, task_type: str) -> Optional[type[Task]]:
        """
        获取任务类，不存在时返回 None

        Args:
            task_type: 任务类型标识

        Returns:
            任务类或 None
        """
        return cls._tasks.get(task_type)

    @classmethod
    def all_types(cls) -> list[str]:
        """获取所有已注册的任务类型"""
        return list(cls._tasks.keys())

    @classmethod
    def all_tasks(cls) -> dict[str, type[Task]]:
        """获取所有已注册的任务类"""
        return cls._tasks.copy()

    @classmethod
    def is_registered(cls, task_type: str) -> bool:
        """检查任务类型是否已注册"""
        return task_type in cls._tasks

    @classmethod
    def clear(cls):
        """清空注册表（仅用于测试）"""
        cls._tasks.clear()
