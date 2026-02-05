# -*- coding: utf-8 -*-
"""
全局常量定义
"""

DEFAULT_TEMPLATE_THRESHOLD = 0.7  # 默认模板匹配阈值
PACK_TEMPLATE_THRESHOLD = 0.75  # 卡包模板匹配阈值（比默认稍低，因为公共图片匹配度较低）
PACK_SERIES_CODES = ["A", "B"]  # 扩充包系列代号（仅用于切换次数控制）
PACK_AUTO_STRATEGIES = ["latest", "hash_balance", "least_used"]  # 自动选包策略
PACK_AUTO_EXCLUDE_SET_CODES = ["A4b"]  # 排除的限时系列
PACK_AUTO_HASH_VIRTUAL_NODES = 32  # 一致性哈希虚拟节点数

# ADB 配置
DEFAULT_ADB_PORT = 5555  # 默认 ADB 端口
DEFAULT_ADB_ADDRESS = "127.0.0.1:5555"  # 默认 ADB 地址
ADB_CONNECT_FAIL_RESTART_THRESHOLD = 3  # 连接失败重启模拟器阈值

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
SWIPE_DURATION_OPEN = 500  # 开包滑动持续时间 (毫秒)（1x速度）
# SWIPE_DURATION_OPEN = 300  # 开包滑动持续时间 (毫秒)（3x速度）
SWIPE_DURATION_REGISTER = 100  # 卡牌登录图鉴滑动持续时间 (毫秒)
DEFAULT_SCROLL_DURATION = 500  # 默认滚动持续时间 (毫秒)
DEFAULT_SCROLL_RATIO = 0.26  # 默认滚动距离占屏幕高度比例
DEFAULT_MAX_SCROLL_ATTEMPTS = 10  # 默认最大滚动尝试次数

# 数据库配置
DEFAULT_DB_NAME = "ptcgp_v2.db"  # 默认数据库文件名

# Web配置
DEFAULT_WEB_HOST = "127.0.0.1"
DEFAULT_WEB_PORT = 8000


# 模板缩放比例
# 注: 模板现在只裁剪不缩放(103x95)，比原来(513x473)小5倍
# 因此比例要放大5倍来补偿
SCALE_PACK_SERIES_SELECT = 1.15  # 旧值: 0.23
SCALE_PACK_LIST = 4.05  # 旧值: 0.81
SCALE_PACK_DETAIL = 5.05  # 旧值: 1.0


# ========== YOLO + 感知哈希识别配置 ==========
# YOLO检测置信度阈值（来自 test_massive_matching.py 实测验证）
YOLO_OBB_THRESHOLD = 0.55
# Hash匹配相似度阈值（来自 test_massive_matching.py 实测验证）
HASH_SIMILARITY_THRESHOLD = 0.75
# Hash匹配相似度最小差距（用于排除相近候选）
HASH_SIMILARITY_GAP_MIN = 0.02

# 高稀有度卡牌范围（用于记录账号卡牌）
HIGH_RARITY_TARGETS = ["RR", "AR", "SR", "SAR", "IM", "UR", "S", "SSR"]
