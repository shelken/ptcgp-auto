"""统一日志模块 - 支持动态上下文（端口、用户名）"""
import logging
import threading

# 线程局部存储，保存当前上下文
_context = threading.local()


class ContextFormatter(logging.Formatter):
    """自定义格式化器，注入端口和用户名上下文"""

    def format(self, record):
        record.port = getattr(_context, 'port', '----')
        record.username = getattr(_context, 'username', '')
        return super().format(record)


def setup_logging(port: int = None, level: str = "INFO"):
    """初始化日志系统

    Args:
        port: ADB 端口号，用于日志上下文
        level: 日志级别 (DEBUG, INFO, WARNING, ERROR)
    """
    log_level = getattr(logging, level.upper(), logging.INFO)

    # 格式：时间 | 等级 | [端口] 用户名 | 消息
    fmt = "%(asctime)s | %(levelname)-5s | [%(port)s] %(username)s| %(message)s"
    datefmt = "%H:%M:%S"

    handler = logging.StreamHandler()
    handler.setFormatter(ContextFormatter(fmt, datefmt))

    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(log_level)

    if port:
        set_port(port)


def set_port(port: int):
    """设置当前上下文的端口号"""
    _context.port = str(port)


def set_username(username: str):
    """设置当前上下文的用户名"""
    _context.username = f"{username} " if username else ""


def get_logger(name: str = None) -> logging.Logger:
    """获取 logger 实例"""
    return logging.getLogger(name)
