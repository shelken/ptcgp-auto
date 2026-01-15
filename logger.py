"""统一日志模块 - 使用 Loguru"""
import sys
import logging
import random
from loguru import logger

# 移除默认 handler，避免重复输出
logger.remove()

# 可用颜色池（排除已被日志级别占用的颜色）
AVAILABLE_COLORS = [
    "cyan", "magenta", "light-blue", "light-magenta",
    "light-cyan", "light-green", "light-yellow", "light-red",
]

# 端口 -> 颜色映射
_port_colors: dict[str, str] = {}
_used_colors: list[str] = []

# 上下文存储
_port = "----"
_port_color = "white"
_username = ""
_initialized = False


def _get_port_color(port: str) -> str:
    """为端口分配颜色（随机不重复）"""
    global _used_colors

    if port in _port_colors:
        return _port_colors[port]

    # 如果颜色用完了，重置可用池
    available = [c for c in AVAILABLE_COLORS if c not in _used_colors]
    if not available:
        _used_colors.clear()
        available = AVAILABLE_COLORS.copy()

    # 随机选择一个颜色
    color = random.choice(available)
    _used_colors.append(color)
    _port_colors[port] = color

    return color


def _format(record):
    """自定义格式"""
    port = record["extra"].get("port", _port)
    username = record["extra"].get("username", _username)
    color = record["extra"].get("port_color", _port_color)

    port_part = f"<{color}>[{port}]</{color}>"
    user_part = f"<{color}>{username}</{color}> " if username else ""

    return (
        "<green>{time:YYYY-MM-DD HH:mm:ss}</green> | "
        "<level>{level: <5}</level> | "
        f"{port_part} {user_part}| "
        "<level>{message}</level>\n"
    )


def setup_logging(port: int = None, level: str = "INFO"):
    """初始化日志系统

    Args:
        port: ADB 端口号，用于日志上下文
        level: 日志级别 (DEBUG, INFO, WARNING, ERROR)
    """
    global _port, _port_color, _initialized

    if port:
        _port = str(port)
        _port_color = _get_port_color(_port)

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


def set_port(port: int):
    """设置当前上下文的端口号"""
    global _port, _port_color
    _port = str(port)
    _port_color = _get_port_color(_port)


def set_username(username: str):
    """设置当前上下文的用户名"""
    global _username
    _username = username


def get_logger(name: str = None):
    """兼容旧 API，返回 loguru logger"""
    return logger
