# -*- coding: utf-8 -*-
"""
全局常量定义
"""

DEFAULT_TEMPLATE_THRESHOLD = 0.7  # 默认模板匹配阈值

# ADB 配置
DEFAULT_ADB_PORT = 5555  # 默认 ADB 端口
DEFAULT_ADB_ADDRESS = "127.0.0.1:5555"  # 默认 ADB 地址

# 应用配置
APP_PACKAGE = "jp.pokemon.pokemontcgp"
APP_ACTIVITY = "com.unity3d.player.UnityPlayerActivity"

# 屏幕配置
BASE_SCREEN_WIDTH = 1080  # 基准分辨率宽度
BASE_SCREEN_HEIGHT = 1920  # 基准分辨率高度
TEMPLATE_BASE_WIDTH = 1080  # 模板基准宽度

# OCR 配置
DEFAULT_OCR_LANGUAGES = ["zh-Hant", "en-US"]  # 默认 OCR 语言
DEFAULT_OCR_LEVEL = "accurate"  # 默认 OCR 识别级别 ("fast" or "accurate")

# 调度配置
DEFAULT_POLL_INTERVAL = 5.0  # 默认轮询间隔 (秒)
DEFAULT_MAX_WORKERS = 4  # 默认最大工作线程数
DEFAULT_TASK_GENERATION_INTERVAL = 60.0  # 默认任务生成间隔 (秒)

# 执行配置
DEFAULT_MAX_RETRIES = 3  # 默认最大重试次数
DEFAULT_RETRY_DELAY = 30.0  # 默认重试延迟 (秒)
DEFAULT_WAIT_AFTER_CLICK = 0.3  # 默认点击后等待时间 (秒)
DEFAULT_LONG_PRESS_DURATION = 3000  # 默认长按持续时间 (毫秒)
DEFAULT_SWIPE_DURATION = 300  # 默认滑动持续时间 (毫秒)
DEFAULT_SCROLL_DURATION = 500  # 默认滚动持续时间 (毫秒)
DEFAULT_SCROLL_RATIO = 0.26  # 默认滚动距离占屏幕高度比例
DEFAULT_MAX_SCROLL_ATTEMPTS = 10  # 默认最大滚动尝试次数

# 数据库配置
DEFAULT_DB_NAME = "ptcgp_v2.db"  # 默认数据库文件名

# 模板缩放比例
SCALE_PACK_SERIES_SELECT = 0.23
SCALE_PACK_LIST = 0.81
SCALE_PACK_DETAIL = 1.0
