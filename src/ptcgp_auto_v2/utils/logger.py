# -*- coding: utf-8 -*-
"""
统一日志模块 - 使用 Loguru

支持按设备/账号显示不同颜色，方便多设备并发时区分日志来源。
"""

import sys
import logging
import threading
from typing import Optional

from loguru import logger

# 移除默认 handler，避免重复输出
logger.remove()

# 可用颜色池（排除已被日志级别占用的颜色）
AVAILABLE_COLORS = [
    "cyan",
    "magenta",
    "light-blue",
    "light-magenta",
    "light-cyan",
    "light-green",
    "light-yellow",
    "light-red",
]

# 线程本地存储，支持多线程并发
_thread_local = threading.local()

# 全局颜色分配
_device_colors: dict[str, str] = {}
_color_index = 0
_color_lock = threading.Lock()

# 是否已初始化
_initialized = False


def _get_context():
    """获取当前线程的上下文"""
    if not hasattr(_thread_local, "device"):
        _thread_local.device = "----"
    if not hasattr(_thread_local, "device_color"):
        _thread_local.device_color = "white"
    if not hasattr(_thread_local, "nickname"):
        _thread_local.nickname = ""
    if not hasattr(_thread_local, "task"):
        _thread_local.task = ""
    return _thread_local


def _allocate_color(color_key: str) -> str:
    """为颜色键分配颜色（线程安全）"""
    global _color_index
    with _color_lock:
        if color_key in _device_colors:
            return _device_colors[color_key]

        if _color_index < len(AVAILABLE_COLORS):
            color = AVAILABLE_COLORS[_color_index]
            _color_index += 1
        else:
            # 颜色用完后，循环使用
            color = AVAILABLE_COLORS[_color_index % len(AVAILABLE_COLORS)]
            _color_index += 1

        _device_colors[color_key] = color
        return color


def _is_rgb_color(color: str) -> bool:
    """判断是否是 #RRGGBB 格式的颜色"""
    return color.startswith("#") and len(color) == 7


def _format_color_tag(color: str, text: str) -> str:
    """生成带颜色的标签，支持预定义颜色和 RGB 格式"""
    if _is_rgb_color(color):
        return f"<fg {color}>{text}</fg {color}>"
    else:
        return f"<{color}>{text}</{color}>"


def _format(record):
    """自定义格式"""
    ctx = _get_context()

    device = record["extra"].get("device", ctx.device)
    nickname = record["extra"].get("nickname", ctx.nickname)
    color = record["extra"].get("device_color", ctx.device_color)
    task = record["extra"].get("task", ctx.task)

    device_part = _format_color_tag(color, f"[{device}]")
    nick_part = _format_color_tag(color, f"[{nickname}]") + " " if nickname else ""
    task_part = f"<cyan>[{task}]</cyan>: " if task else ""

    return (
        "<green>{time:YYYY-MM-DD HH:mm:ss}</green> | "
        "<level>{level: <5}</level> | "
        f"{device_part} {nick_part}"
        f"{task_part}"
        "<level>{message}</level>\n"
    )


def setup_logging(level: str = "INFO") -> None:
    """
    初始化日志系统

    Args:
        level: 日志级别 (DEBUG, INFO, WARNING, ERROR)
    """
    global _initialized

    # 避免重复添加 handler
    if not _initialized:
        logger.add(
            sys.stderr,
            format=_format,
            level=level.upper(),
            colorize=True,
        )
        _initialized = True

    # 禁用第三方库的调试日志
    logging.getLogger("PIL").setLevel(logging.WARNING)
    logging.getLogger("PIL.PngImagePlugin").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("uiautomator2").setLevel(logging.WARNING)


def set_context(
    device: str | None = None,
    nickname: str | None = None,
    color_key: str | None = None,
    color: str | None = None,
    task: str | None = None,
) -> None:
    """
    设置当前线程的日志上下文

    Args:
        device: 设备显示名
        nickname: 账号昵称
        color_key: 颜色稳定键
        color: 设备颜色（可选，自动分配）
        task: 当前任务名称
    """
    ctx = _get_context()

    if device is not None:
        ctx.device = str(device)

    if color_key is not None or device is not None:
        resolved_color_key = str(color_key if color_key is not None else device)
        ctx.device_color = color if color else _allocate_color(resolved_color_key)

    if nickname is not None:
        ctx.nickname = nickname

    if task is not None:
        ctx.task = task


def clear_context():
    """清除当前线程的日志上下文"""
    ctx = _get_context()
    ctx.device = "----"
    ctx.device_color = "white"
    ctx.nickname = ""
    ctx.task = ""


def get_logger(name: str) -> "logger":
    """
    获取日志器

    Args:
        name: 日志器名称（模块名）

    Returns:
        绑定了模块名的 loguru logger
    """
    return logger.bind(name=name)


# 兼容标准 logging 的拦截器
class InterceptHandler(logging.Handler):
    """拦截标准 logging 并转发到 loguru"""

    def emit(self, record):
        # 获取对应的 loguru 级别
        try:
            level = logger.level(record.levelname).name
        except ValueError:
            level = record.levelno

        # 查找调用者
        frame, depth = logging.currentframe(), 2
        while frame.f_code.co_filename == logging.__file__:
            frame = frame.f_back
            depth += 1

        logger.opt(depth=depth, exception=record.exc_info).log(
            level, record.getMessage()
        )


def intercept_standard_logging():
    """拦截所有标准 logging 输出到 loguru"""
    logging.basicConfig(handlers=[InterceptHandler()], level=0, force=True)
