# -*- coding: utf-8 -*-
"""
日志工具模块
"""

import logging
import sys
from typing import Optional


def setup_logging(
    level: str = "INFO",
    format_string: Optional[str] = None,
) -> None:
    """
    配置日志系统

    Args:
        level: 日志级别
        format_string: 日志格式字符串
    """
    if format_string is None:
        format_string = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"

    log_level = getattr(logging, level.upper(), logging.INFO)

    logging.basicConfig(
        level=log_level,
        format=format_string,
        datefmt="%Y-%m-%d %H:%M:%S",
        handlers=[
            logging.StreamHandler(sys.stdout),
        ],
    )

    # 降低第三方库的日志级别
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("PIL").setLevel(logging.WARNING)
    logging.getLogger("adbutils").setLevel(logging.WARNING)


def get_logger(name: str) -> logging.Logger:
    """
    获取日志器

    Args:
        name: 日志器名称

    Returns:
        Logger 实例
    """
    return logging.getLogger(name)
