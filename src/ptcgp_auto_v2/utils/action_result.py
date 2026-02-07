# -*- coding: utf-8 -*-
"""
动作结果数据结构
"""

from dataclasses import dataclass
from typing import Optional, Protocol, Type, overload

DEFAULT_WAIT_SECONDS = 1.0  # 默认等待时间(秒)


class _OkCallable(Protocol):
    """兼容 ActionResult.ok 的调用签名。"""

    def __call__(self, wait: float = DEFAULT_WAIT_SECONDS) -> "ActionResult": ...


class _OkDescriptor:
    """ActionResult.ok 兼容访问器。"""

    @overload
    def __get__(self, instance: None, owner: Type["ActionResult"]) -> _OkCallable: ...

    @overload
    def __get__(
        self, instance: "ActionResult", owner: Type["ActionResult"]
    ) -> bool: ...

    def __get__(
        self, instance: Optional["ActionResult"], owner: Type["ActionResult"]
    ) -> bool | _OkCallable:
        if instance is None:

            def _create(wait: float = DEFAULT_WAIT_SECONDS) -> "ActionResult":
                """创建成功结果"""
                return owner(success=True, should_wait=wait)

            return _create
        return instance.success


@dataclass
class ActionResult:
    """
    单次动作执行结果

    用于 handle_page 方法返回执行状态。
    """

    success: bool = True
    error: Optional[str] = None
    should_wait: float = DEFAULT_WAIT_SECONDS  # 建议等待时间（秒）

    ok = _OkDescriptor()

    @classmethod
    def fail(cls, error: str) -> "ActionResult":
        """创建失败结果"""
        return cls(success=False, error=error)

    @classmethod
    def wait(cls, seconds: float) -> "ActionResult":
        """创建需要等待的结果"""
        return cls(success=True, should_wait=seconds)
