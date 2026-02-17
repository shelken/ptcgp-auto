# -*- coding: utf-8 -*-
"""
Hook 机制基础定义

提供任务执行前后插入逻辑的通用接口与上下文。
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ptcgp_auto_v2.core.device_pool import Device
    from ptcgp_auto_v2.core.executor import BaseExecutor
    from ptcgp_auto_v2.core.task_base import Task
    from ptcgp_auto_v2.db.models import Account


class HookResult(Enum):
    """Hook 执行结果"""

    CONTINUE = "continue"  # 继续执行主任务
    ABORT = "abort"  # 中断执行，任务标记为失败
    INSERT_TASK = "insert"  # 需要插入并执行前置任务，暂停当前任务
    DELAY = "delay"  # 延后当前任务下一次执行时间
    SKIP = "skip"  # 跳过当前任务，释放调度机会（不重试）


@dataclass
class HookContext:
    """
    Hook 执行上下文

    提供 Hook 所需的全部信息和操作能力。
    """

    device: "Device"  # 当前设备
    account: "Account"  # 当前账号
    task: "Task"  # 当前任务
    executor: "BaseExecutor"  # 执行器（用于插入任务等操作）


class Hook(ABC):
    """Hook 基类"""

    @abstractmethod
    def run(self, context: HookContext) -> tuple[HookResult, dict]:
        """
        执行 Hook 逻辑

        Args:
            context: 执行上下文

        Returns:
            (HookResult, data) 指示后续操作
            - HookResult.CONTINUE: data 为空
            - HookResult.ABORT: data 包含 error 信息
            - HookResult.INSERT_TASK: data 包含 task_type, priority 等
            - HookResult.DELAY: data 包含 delay_seconds 或 run_at
            - HookResult.SKIP: data 包含 reason，任务跳过但不失败
        """
        raise NotImplementedError
