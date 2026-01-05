"""
PTCGP 自动化脚本配置
"""

from importlib import import_module

# 语言配置（可选: "zh_Hant", "en_US"）
LANGUAGE = "zh_Hant"

# ADB 连接配置
ADB_HOST = "127.0.0.1"
ADB_PORT = 5555  # BlueStacks Air 默认端口，可能需要根据实际情况调整

# 等待时间配置（秒）
WAIT_AFTER_CLICK = 0.5  # 点击后等待
WAIT_PAGE_TRANSITION = 1.5  # 页面切换等待
WAIT_BATTLE_CHECK_INTERVAL = 5  # 对局中检测间隔（默认10秒）
WAIT_BATTLE_TIMEOUT = 600  # 对局超时时间（10分钟）

# 屏幕分辨率（BlueStacks 默认）
SCREEN_WIDTH = 1080
SCREEN_HEIGHT = 1920

# 模板基准分辨率（模板图片是在此分辨率下截取的）
TEMPLATE_BASE_WIDTH = 1080

# OCR 配置 (Apple Vision Framework)
# Vision Framework 原生支持 Apple Silicon 硬件加速，无需额外配置
OCR_RECOGNITION_LEVEL = "accurate"  # "accurate" 或 "fast"
OCR_LANGUAGES = ["zh-Hant", "en-US"]  # 繁体中文 + 英文

# 模板匹配阈值（0-1，越高越严格）
TEMPLATE_THRESHOLD = 0.8

# 调试模式
DEBUG = True  # 开启后会保存截图和识别结果
DEBUG_DIR = "debug_output"

# 自动开启自动对战（对战中检测到未开启时自动点击开启）
AUTO_ENABLE_AUTO_BATTLE = True

# 弹窗按钮文字（用于滚动循环中检测遮挡弹窗）
POPUP_BUTTONS = ["OK", "确认", "確認", "取消"]

# 动态加载语言配置
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
