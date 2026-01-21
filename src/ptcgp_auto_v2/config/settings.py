# -*- coding: utf-8 -*-
"""
运行时配置模块

管理应用程序的运行时配置。
"""

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional

logger = logging.getLogger(__name__)

# 全局配置实例
_settings: Optional["Settings"] = None


@dataclass
class Settings:
    """
    应用程序配置

    包含所有运行时可配置的参数。
    """

    # ADB 配置
    device_addresses: List[str] = field(default_factory=lambda: ["127.0.0.1:5555"])

    # 应用配置
    app_package: str = "jp.pokemon.pokemontcgp"
    app_activity: str = "com.unity3d.player.UnityPlayerActivity"

    # 屏幕配置
    # 基准分辨率：用于坐标比例计算的参考值（模板图片基于此分辨率截取）
    base_screen_width: int = 1080
    base_screen_height: int = 1920
    template_base_width: int = 1080

    # 识别配置
    ocr_languages: List[str] = field(default_factory=lambda: ["zh-Hant", "en-US"])
    ocr_recognition_level: str = "accurate"  # "fast" or "accurate"
    template_threshold: float = 0.8

    # 调度配置
    poll_interval: float = 5.0
    max_workers: int = 4
    task_generation_interval: float = 60.0

    # 执行配置
    max_retries: int = 3
    retry_delay: float = 30.0
    wait_after_click: float = 0.3

    # 路径配置
    templates_dir: Path = field(default_factory=lambda: Path("templates"))
    data_dir: Path = field(default_factory=lambda: Path("data"))

    # 日志配置
    log_level: str = "INFO"
    debug: bool = False

    # 模板缩放比例
    scale_pack_series_select: float = 0.23
    scale_pack_list: float = 0.81
    scale_pack_detail: float = 1.0

    # 最大尝试次数
    max_scroll_attempts: int = 10

    def __post_init__(self):
        """初始化后处理"""
        # 确保路径是 Path 对象
        if isinstance(self.templates_dir, str):
            self.templates_dir = Path(self.templates_dir)
        if isinstance(self.data_dir, str):
            self.data_dir = Path(self.data_dir)

    @classmethod
    def from_env(cls) -> "Settings":
        """从环境变量加载配置"""
        import os

        settings = cls()

        # 从环境变量覆盖配置
        if os.getenv("PTCGP_DEVICES"):
            settings.device_addresses = os.getenv("PTCGP_DEVICES").split(",")

        if os.getenv("PTCGP_DEBUG"):
            settings.debug = os.getenv("PTCGP_DEBUG").lower() in ("true", "1", "yes")
            if settings.debug:
                settings.log_level = "DEBUG"

        if os.getenv("PTCGP_MAX_WORKERS"):
            settings.max_workers = int(os.getenv("PTCGP_MAX_WORKERS"))

        return settings

    def configure_logging(self):
        """配置日志系统（使用 loguru）"""
        from ptcgp_auto_v2.utils.logger import setup_logging, intercept_standard_logging

        # 初始化 loguru 日志
        setup_logging(level=self.log_level)

        # 拦截标准 logging 输出到 loguru
        intercept_standard_logging()


def get_settings() -> Settings:
    """
    获取全局配置实例

    Returns:
        Settings 实例
    """
    global _settings

    if _settings is None:
        _settings = Settings.from_env()

    return _settings


def set_settings(settings: Settings):
    """
    设置全局配置实例

    Args:
        settings: Settings 实例
    """
    global _settings
    _settings = settings
