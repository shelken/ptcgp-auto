# -*- coding: utf-8 -*-
"""
核心框架模块。

使用惰性导出，避免导入子模块时触发整层初始化导致循环依赖。
"""

from importlib import import_module
from typing import Any

__all__ = [
    "Device",
    "DevicePool",
    "StatefulTask",
    "Task",
    "TaskRegistry",
    "TaskResult",
    "ActionResult",
    "TaskState",
    "TaskStatus",
    "Scheduler",
    "AccountExecutor",
]

_EXPORT_MODULES = {
    "Device": "ptcgp_auto_v2.core.device_pool",
    "DevicePool": "ptcgp_auto_v2.core.device_pool",
    "StatefulTask": "ptcgp_auto_v2.core.stateful_task",
    "Task": "ptcgp_auto_v2.core.task_base",
    "TaskRegistry": "ptcgp_auto_v2.core.task_base",
    "TaskResult": "ptcgp_auto_v2.core.task_base",
    "ActionResult": "ptcgp_auto_v2.core.task_base",
    "TaskState": "ptcgp_auto_v2.core.task_state",
    "TaskStatus": "ptcgp_auto_v2.core.task_status",
    "Scheduler": "ptcgp_auto_v2.core.scheduler",
    "AccountExecutor": "ptcgp_auto_v2.core.executor",
}


def __getattr__(name: str) -> Any:
    """按需导出核心符号。"""
    module_name = _EXPORT_MODULES.get(name)
    if module_name is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    return getattr(import_module(module_name), name)
