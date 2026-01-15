"""统一日志模块 - 使用 Loguru"""
import sys
import logging
from loguru import logger

# 移除默认 handler，避免重复输出
logger.remove()

# 上下文存储
_port = "----"
_username = ""
_initialized = False


def _format(record):
    """自定义格式"""
    port = record["extra"].get("port", _port)
    username = record["extra"].get("username", _username)
    user_part = f"{username} " if username else ""
    return (
        "<green>{time:YYYY-MM-DD HH:mm:ss}</green> | "
        "<level>{level: <5}</level> | "
        f"[{port}] {user_part}| "
        "<level>{message}</level>\n"
    )


def setup_logging(port: int = None, level: str = "INFO"):
    """初始化日志系统

    Args:
        port: ADB 端口号，用于日志上下文
        level: 日志级别 (DEBUG, INFO, WARNING, ERROR)
    """
    global _port, _initialized

    if port:
        _port = str(port)

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
    global _port
    _port = str(port)


def set_username(username: str):
    """设置当前上下文的用户名"""
    global _username
    _username = username


def get_logger(name: str = None):
    """兼容旧 API，返回 loguru logger"""
    return logger
