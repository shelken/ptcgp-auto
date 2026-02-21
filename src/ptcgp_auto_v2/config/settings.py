# -*- coding: utf-8 -*-
"""
运行时配置模块

管理应用程序的运行时配置。
"""

import logging
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional

from ptcgp_auto_v2.config.constants import (
    APP_ACTIVITY,
    APP_PACKAGE,
    BASE_SCREEN_HEIGHT,
    BASE_SCREEN_WIDTH,
    DEFAULT_ADB_ADDRESS,
    DEFAULT_DB_NAME,
    DEFAULT_LOCALE,
    DEFAULT_MAX_RETRIES,
    DEFAULT_MAX_SCROLL_ATTEMPTS,
    DEFAULT_MAX_WORKERS,
    DEFAULT_OCR_LANGUAGES,
    DEFAULT_OCR_LEVEL,
    DEFAULT_POLL_INTERVAL,
    DEFAULT_RETRY_DELAY,
    DEFAULT_TASK_GENERATION_INTERVAL,
    DEFAULT_TEMPLATE_THRESHOLD,
    DEFAULT_WAIT_AFTER_CLICK,
    DEFAULT_WEB_HOST,
    DEFAULT_WEB_PORT,
    SCALE_PACK_DETAIL,
    SCALE_PACK_LIST,
    SCALE_PACK_SERIES_SELECT,
    TEMPLATE_BASE_WIDTH,
)

logger = logging.getLogger(__name__)

# 全局配置实例
_settings: Optional["Settings"] = None
_dotenv_loaded = False


def build_wecom_webhook_url_from_key(key: str) -> str:
    """将企微 webhook key 转换为完整 webhook URL。"""
    return f"https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key={key}"


def apply_webhook_cli_overrides(
    webhook_url: Optional[str] = None,
    notify_key: Optional[str] = None,
) -> None:
    """应用 webhook CLI 参数覆盖（优先级最高）。"""
    if webhook_url:
        os.environ["PTCGP_WEBHOOK_URL"] = webhook_url.strip()
        return

    if notify_key:
        key = notify_key.strip()
        if not key:
            return
        os.environ["PTCGP_WEBHOOK_URL"] = build_wecom_webhook_url_from_key(key)
        os.environ["PTCGP_NOTIFY_KEY"] = key
        os.environ["NOTIFY_KEY"] = key


def load_dotenv() -> None:
    """加载项目根目录 .env 到环境变量（不覆盖已有环境变量）。"""
    global _dotenv_loaded
    if _dotenv_loaded:
        return

    env_path = Path.cwd() / ".env"
    if not env_path.exists():
        _dotenv_loaded = True
        return

    for line in env_path.read_text(encoding="utf-8").splitlines():
        raw = line.strip()
        if not raw or raw.startswith("#") or "=" not in raw:
            continue

        key, _, value = raw.partition("=")
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if not key:
            continue
        os.environ.setdefault(key, value)

    _dotenv_loaded = True


def get_project_root() -> Path:
    """获取项目根目录（包含 main_v2.py 的目录）"""
    # 从 settings.py 向上查找 4 级：config -> ptcgp_auto_v2 -> src -> 项目根目录
    return Path(__file__).parent.parent.parent.parent


@dataclass
class Settings:
    """
    应用程序配置

    包含所有运行时可配置的参数。
    """

    # ADB 配置
    device_addresses: List[str] = field(default_factory=lambda: [DEFAULT_ADB_ADDRESS])

    # 应用配置
    app_package: str = APP_PACKAGE
    app_activity: str = APP_ACTIVITY

    @property
    def app_data_dir(self) -> str:
        """应用数据目录路径"""
        return f"/data/data/{self.app_package}"

    @property
    def device_xml_path(self) -> str:
        """设备账号 XML 路径"""
        return f"{self.app_data_dir}/shared_prefs/deviceAccount:.xml"

    @property
    def shared_prefs_dir(self) -> str:
        """shared_prefs 目录路径"""
        return f"{self.app_data_dir}/shared_prefs"

    @property
    def main_activity(self) -> str:
        """应用主 Activity"""
        return f"{self.app_package}/{self.app_activity}"

    @property
    def files_to_clean_on_switch(self) -> list[str]:
        """切换账号时需要清理的文件列表"""
        return [
            f"{self.app_data_dir}/files/PersistedInstallation.*.json",
            f"{self.app_data_dir}/files/UserPreferences/v1/MissionUserPrefs",
        ]

    # Web配置
    web_host: str = DEFAULT_WEB_HOST
    web_port: int = DEFAULT_WEB_PORT

    # 屏幕配置
    # 基准分辨率：用于坐标比例计算的参考值（模板图片基于此分辨率截取）
    base_screen_width: int = BASE_SCREEN_WIDTH
    base_screen_height: int = BASE_SCREEN_HEIGHT
    template_base_width: int = TEMPLATE_BASE_WIDTH

    # 识别配置
    ocr_languages: List[str] = field(default_factory=lambda: DEFAULT_OCR_LANGUAGES)
    ocr_recognition_level: str = DEFAULT_OCR_LEVEL  # "fast" or "accurate"
    template_threshold: float = DEFAULT_TEMPLATE_THRESHOLD

    # 语言配置
    locale: str = DEFAULT_LOCALE  # 默认界面语言 (对应 locales/ 下的文件名)

    # 未配置开包目标时的自动选包策略
    # 可选值: latest / hash_balance / least_used
    # latest 自动选最新包
    # hash_balance 一致性hash均衡所有包的选择
    pack_auto_strategy: str = "hash_balance"

    # 调度配置
    poll_interval: float = DEFAULT_POLL_INTERVAL
    max_workers: int = DEFAULT_MAX_WORKERS
    task_generation_interval: float = DEFAULT_TASK_GENERATION_INTERVAL

    # 自动创建账号
    auto_create_accounts: bool = False
    max_accounts: int = 100  # 自动创建账号的最大数量上限

    # 自动扩缩容配置
    auto_scale_emulators: bool = True
    auto_scale_instance_prefix: str = "auto-"
    auto_scale_min_idle_devices: int = 1
    auto_scale_max_devices: int = 2
    auto_scale_pending_step: int = 10
    auto_scale_eval_interval_seconds: int = 60
    auto_scale_idle_seconds: int = 60

    # 执行配置
    max_retries: int = DEFAULT_MAX_RETRIES
    retry_delay: float = DEFAULT_RETRY_DELAY
    wait_after_click: float = DEFAULT_WAIT_AFTER_CLICK

    # 路径配置
    templates_dir: Path = field(default_factory=lambda: Path("templates"))
    data_dir: Path = field(default_factory=lambda: Path("data"))
    db_name: str = DEFAULT_DB_NAME

    @property
    def db_path(self) -> Path:
        """数据库文件完整路径"""
        # 使用项目根目录下的 data 目录
        root = get_project_root()
        db_dir = root / self.data_dir
        db_dir.mkdir(parents=True, exist_ok=True)
        return db_dir / self.db_name

    # 日志配置
    log_level: str = "INFO"
    debug: bool = False

    # 模板缩放比例
    scale_pack_series_select: float = SCALE_PACK_SERIES_SELECT
    scale_pack_list: float = SCALE_PACK_LIST
    scale_pack_detail: float = SCALE_PACK_DETAIL

    # 最大尝试次数
    max_scroll_attempts: int = DEFAULT_MAX_SCROLL_ATTEMPTS

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
        load_dotenv()

        settings = cls()

        # 从环境变量覆盖配置
        devices_env = os.getenv("PTCGP_DEVICES")
        if devices_env:
            settings.device_addresses = devices_env.split(",")

        debug_env = os.getenv("PTCGP_DEBUG")
        if debug_env:
            settings.debug = debug_env.lower() in ("true", "1", "yes")
            if settings.debug:
                settings.log_level = "DEBUG"

        max_workers_env = os.getenv("PTCGP_MAX_WORKERS")
        if max_workers_env:
            settings.max_workers = int(max_workers_env)

        web_host_env = os.getenv("PTCGP_WEB_HOST")
        if web_host_env:
            settings.web_host = web_host_env

        web_port_env = os.getenv("PTCGP_WEB_PORT")
        if web_port_env:
            settings.web_port = int(web_port_env)

        return settings

    def configure_logging(self):
        """配置日志系统（使用 loguru）"""
        from ptcgp_auto_v2.utils.logger import intercept_standard_logging, setup_logging

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
    load_dotenv()

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
    load_dotenv()
    _settings = settings
