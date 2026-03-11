# -*- coding: utf-8 -*-
"""
核心框架模块

包含调度器、设备池、任务执行器和任务基类。
"""

from ptcgp_auto_v2.core.device_pool import Device, DevicePool
from ptcgp_auto_v2.core.task_base import Task, TaskRegistry, TaskResult, ActionResult
from ptcgp_auto_v2.core.task_status import TaskStatus
from ptcgp_auto_v2.core.scheduler import Scheduler
from ptcgp_auto_v2.core.executor import AccountExecutor

__all__ = [
    "Device",
    "DevicePool",
    "Task",
    "TaskRegistry",
    "TaskResult",
    "ActionResult",
    "TaskStatus",
    "Scheduler",
    "AccountExecutor",
]
