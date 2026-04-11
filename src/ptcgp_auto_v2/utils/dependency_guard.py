# -*- coding: utf-8 -*-
"""
底层依赖调用护栏

负责为同步外部库调用提供超时、异常日志和 failfast 行为。
"""

import logging
import threading
import traceback
from queue import Empty, Queue
from typing import Callable, TypeVar

T = TypeVar("T")


class DependencyCallError(RuntimeError):
    """底层依赖调用失败。"""


class DependencyCallTimeoutError(DependencyCallError):
    """底层依赖调用超时。"""


def run_failfast_call(
    logger: logging.Logger,
    operation: str,
    timeout_seconds: float,
    func: Callable[[], T],
) -> T:
    """执行底层同步调用，超时或异常时直接抛错。"""
    result_queue: Queue[tuple[str, object, str | None]] = Queue(maxsize=1)

    def _runner():
        try:
            result_queue.put(("ok", func(), None))
        except Exception as exc:
            result_queue.put(("error", exc, traceback.format_exc()))

    thread = threading.Thread(
        target=_runner,
        name=f"dep-call:{operation}",
        daemon=True,
    )
    thread.start()
    thread.join(timeout_seconds)

    if thread.is_alive():
        logger.error("底层调用超时: op=%s timeout=%.1fs", operation, timeout_seconds)
        raise DependencyCallTimeoutError(f"底层调用超时: {operation}")

    try:
        status, payload, tb = result_queue.get_nowait()
    except Empty as exc:
        logger.error("底层调用未返回结果: op=%s", operation)
        raise DependencyCallError(f"底层调用未返回结果: {operation}") from exc

    if status == "error":
        logger.error("底层调用异常: op=%s\n%s", operation, (tb or "").rstrip())
        raise DependencyCallError(f"底层调用异常: {operation}") from payload  # type: ignore[arg-type]

    return payload  # type: ignore[return-value]
