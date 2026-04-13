"""统一日志模块 - 使用 Loguru"""

import sys
import logging
import random
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

# 端口 -> 颜色映射
_port_colors: dict[str, str] = {}

# 上下文存储
_port = "----"
_port_color = "white"
_username = ""
_level = ""
_initialized = False


def allocate_colors(ports: list[str]) -> dict[str, str]:
    """为多个端口分配不重复的颜色（父进程调用）

    Args:
        ports: 端口号列表

    Returns:
        端口 -> 颜色的映射
    """
    result = {}
    for i, port in enumerate(ports):
        if i < len(AVAILABLE_COLORS):
            color = AVAILABLE_COLORS[i]
        else:
            # 颜色用完后，生成随机 RGB 颜色（避开太暗的颜色）
            r = random.randint(100, 255)
            g = random.randint(100, 255)
            b = random.randint(100, 255)
            color = f"#{r:02x}{g:02x}{b:02x}"
        result[port] = color
    return result


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
    port = record["extra"].get("port", _port)
    username = record["extra"].get("username", _username)
    level = record["extra"].get("level", _level)
    color = record["extra"].get("port_color", _port_color)

    port_part = _format_color_tag(color, f"[{port}]")
    user_part = _format_color_tag(color, username) + " " if username else ""
    level_part = _format_color_tag(color, f"[{level}]") + " " if level else ""

    return (
        "<green>{time:YYYY-MM-DD HH:mm:ss}</green> | "
        "<level>{level: <5}</level> | "
        f"{port_part} {user_part}{level_part}| "
        "<level>{message}</level>\n"
    )


def setup_logging(port: int = None, level: str = "INFO", color: str = None):
    """初始化日志系统

    Args:
        port: ADB 端口号，用于日志上下文
        level: 日志级别 (DEBUG, INFO, WARNING, ERROR)
        color: 端口颜色（由父进程分配，支持预定义颜色或 #RRGGBB 格式）
    """
    global _port, _port_color, _initialized

    if port:
        _port = str(port)
        # 优先使用传入的颜色，否则使用默认白色
        _port_color = color if color else "white"
        _port_colors[_port] = _port_color

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


def set_username(username: str):
    """设置当前上下文的用户名"""
    global _username
    _username = username


def set_level(level: str):
    """设置当前上下文的等级"""
    global _level
    _level = level if level else ""


def get_logger(name: str = None):
    """兼容旧 API，返回 loguru logger"""
    return logger
