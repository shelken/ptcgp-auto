"""
PTCGP 自动化脚本配置

静态配置项（不通过 CLI/.env 配置）放在这里。
运行时配置项由 settings.py 管理，通过 CLI/环境变量/.env 配置。
"""

from importlib import import_module

# ============================================================
# 运行时配置（由 settings.py 动态设置，这里只是默认值）
# ============================================================

# 语言配置（可选: "zh_Hant", "en_US"）
LANGUAGE = "zh_Hant"

# ADB 连接配置
ADB_HOST = "127.0.0.1"
ADB_PORT = 5555

# 日志级别 (DEBUG, INFO, WARNING, ERROR)
LOG_LEVEL = "INFO"

# 向后兼容：DEBUG 变量（当 LOG_LEVEL 为 DEBUG 时为 True）
# 注意：修改 LOG_LEVEL 后需要调用 update_debug_flag()
DEBUG = False


def update_debug_flag():
    """根据 LOG_LEVEL 更新 DEBUG 标志"""
    global DEBUG
    DEBUG = LOG_LEVEL == "DEBUG"

# 通知配置
NOTIFICATION_ENABLED = False
NOTIFICATION_WEBHOOK_KEY = ""
NOTIFICATION_SOUND = True

# 自动开启自动对战
AUTO_ENABLE_AUTO_BATTLE = True

# ============================================================
# 静态配置（不通过 CLI/.env 配置）
# ============================================================

# 等待时间配置（秒）
WAIT_AFTER_CLICK = 0.5  # 点击后等待
WAIT_PAGE_TRANSITION = 1  # 页面切换等待
WAIT_BATTLE_CHECK_INTERVAL = 2  # 对局中检测间隔
WAIT_BATTLE_TIMEOUT = 600  # 对局超时时间（10分钟）

# 无法识别界面的阈值（连续多少次触发通知）
UNRECOGNIZED_THRESHOLD = 10

# 屏幕分辨率（BlueStacks 默认）
SCREEN_WIDTH = 1080
SCREEN_HEIGHT = 1920

# 模板基准分辨率（模板图片是在此分辨率下截取的）
TEMPLATE_BASE_WIDTH = 1080

# OCR 配置 (Apple Vision Framework)
OCR_RECOGNITION_LEVEL = "accurate"  # "accurate" 或 "fast"
OCR_LANGUAGES = ["zh-Hant", "en-US"]  # 繁体中文 + 英文

# 模板匹配阈值（0-1，越高越严格）
TEMPLATE_THRESHOLD = 0.8

# 调试输出目录
DEBUG_DIR = "debug_output"

# 弹窗按钮文字（用于滚动循环中检测遮挡弹窗）
POPUP_BUTTONS = ["OK", "确认", "確認", "取消"]

# ============================================================
# 动态加载语言配置
# ============================================================

_locale = None
BATTLE_LEVELS = None
PAGES = None
TEXT_PATTERNS = None
DECK_KEYWORD = None
SERIES = None


def load_language(lang: str = None):
    """加载语言配置"""
    global LANGUAGE, _locale, BATTLE_LEVELS, PAGES, TEXT_PATTERNS, DECK_KEYWORD, SERIES
    if lang:
        LANGUAGE = lang
    _locale = import_module(f"locales.{LANGUAGE}")
    BATTLE_LEVELS = _locale.BATTLE_LEVELS
    PAGES = _locale.PAGES
    TEXT_PATTERNS = _locale.TEXT_PATTERNS
    DECK_KEYWORD = _locale.DECK_KEYWORD
    SERIES = _locale.SERIES


# 默认加载
load_language()
