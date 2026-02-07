# -*- coding: utf-8 -*-
"""
动作结果数据结构
"""

from dataclasses import dataclass
from typing import Optional

DEFAULT_WAIT_SECONDS = 1.0  # 默认等待时间(秒)


@dataclass
class ActionResult:
    """
    单次动作执行结果

    用于 handle_page 方法返回执行状态。
    """

    success: bool = True
    error: Optional[str] = None
    should_wait: float = DEFAULT_WAIT_SECONDS  # 建议等待时间（秒）

    @classmethod
    def ok(cls, wait: float = DEFAULT_WAIT_SECONDS) -> "ActionResult":
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
