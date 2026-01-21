# -*- coding: utf-8 -*-
"""
任务基类与注册表模块

定义可插拔任务的接口规范和注册机制。
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Callable, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from ptcgp_auto_v2.db.models import Account


class ResetType(Enum):
    """任务重置类型"""

    DAILY = "daily"  # 每日重置
    WEEKLY = "weekly"  # 每周重置
    ONCE = "once"  # 一次性任务


class TaskStatus(Enum):
    """任务实例状态"""

    PENDING = "pending"  # 待执行
    BLOCKED = "blocked"  # 被阻塞（等待前置任务完成）
    RUNNING = "running"  # 执行中
    COMPLETED = "completed"  # 已完成
    FAILED = "failed"  # 失败


@dataclass
class ActionResult:
    """
    单次动作执行结果

    用于 handle_page 方法返回执行状态。
    """

    success: bool = True
    error: Optional[str] = None
    should_wait: float = 1.0  # 建议等待时间（秒）

    @classmethod
    def ok(cls, wait: float = 1.0) -> "ActionResult":
        """创建成功结果"""
        return cls(success=True, should_wait=wait)

    @classmethod
    def fail(cls, error: str) -> "ActionResult":
        """创建失败结果"""
        return cls(success=False, error=error)

    @classmethod
    def wait(cls, seconds: float) -> "ActionResult":
        """创建需要等待的结果"""
        return cls(success=True, should_wait=seconds)


@dataclass
class TaskResult:
    """
    任务执行结果

    用于 execute 方法返回最终状态。
    """

    success: bool
    error: Optional[str] = None
    data: dict = field(default_factory=dict)  # 附加数据

    @classmethod
    def ok(cls, **data) -> "TaskResult":
        """创建成功结果"""
        return cls(success=True, data=data)

    @classmethod
    def fail(cls, error: str, **data) -> "TaskResult":
        """创建失败结果"""
        return cls(success=False, error=error, data=data)


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
    max_iterations: int = 100

    # 连续未知页面上限
    max_unknown_pages: int = 30

    def __init__(self, adb, recognizer, page_detector):
        """
        初始化任务

        Args:
            adb: ADB 控制器实例
            recognizer: 识别器实例
            page_detector: 页面检测器实例
        """
        self.adb = adb
        self.recognizer = recognizer
        self.page_detector = page_detector
        self._account: Optional["Account"] = None
        self._handlers: dict[str, Callable[[dict], ActionResult]] = {}

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

    def on_complete(self, result: TaskResult):
        """
        任务完成后的钩子方法

        Args:
            result: 任务执行结果
        """
        pass

    def execute(self) -> TaskResult:
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

        self.on_start()
        unknown_count = 0

        for iteration in range(self.max_iterations):
            # 检查目标状态
            if self.is_completed():
                result = TaskResult.ok(iterations=iteration)
                self.on_complete(result)
                return result

            # 识别当前页面
            page_name, page_info = self.page_detector.detect()

            # 处理未知页面
            if page_name == "unknown":
                unknown_count += 1
                if unknown_count >= self.max_unknown_pages:
                    result = TaskResult.fail(
                        f"连续 {self.max_unknown_pages} 次未识别页面",
                        iterations=iteration,
                    )
                    self.on_complete(result)
                    return result
                # 尝试返回键
                self.adb.press_back()
                time.sleep(1)
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
                self.on_complete(result)
                return result

            # 等待
            time.sleep(action_result.should_wait)

        # 超过最大迭代次数
        result = TaskResult.fail(
            f"超过最大迭代次数 {self.max_iterations}", iterations=self.max_iterations
        )
        self.on_complete(result)
        return result


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
