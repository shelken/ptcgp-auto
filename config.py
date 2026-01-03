"""
PTCGP 自动化脚本配置
"""

from importlib import import_module

# 语言配置（可选: "zh_Hant", "en_US"）
LANGUAGE = "en_US"

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

# OCR 配置 (Apple Vision Framework)
# Vision Framework 原生支持 Apple Silicon 硬件加速，无需额外配置
OCR_RECOGNITION_LEVEL = "accurate"  # "accurate" 或 "fast"
OCR_LANGUAGES = ["zh-Hant", "en-US"]  # 繁体中文 + 英文

# 模板匹配阈值（0-1，越高越严格）
TEMPLATE_THRESHOLD = 0.8

# 动态加载语言配置
_locale = import_module(f"locales.{LANGUAGE}")
BATTLE_LEVELS = _locale.BATTLE_LEVELS
PAGES = _locale.PAGES
TEXT_VARIANTS = _locale.TEXT_VARIANTS
DECK_KEYWORD = _locale.DECK_KEYWORD

# 调试模式
DEBUG = True  # 开启后会保存截图和识别结果
DEBUG_DIR = "debug_output"
