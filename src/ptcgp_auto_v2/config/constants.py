# -*- coding: utf-8 -*-
"""
全局常量定义

注意：语言相关配置已统一迁移到 lang.py，请从该模块导入。
本文件保留重新导出以保持向后兼容。
"""

# 从 lang.py 重新导出语言配置（单一真相来源）
from ptcgp_auto_v2.config.lang import (
    DEFAULT_LANG_KEY,
    DEFAULT_LOCALE,
    DEFAULT_OCR_LANGUAGES,
    WEB_LANG_TO_DB_LABEL_KEYS,
)

DEFAULT_TEMPLATE_THRESHOLD = 0.7  # 默认模板匹配阈值
PACK_TEMPLATE_THRESHOLD = 0.7  # 卡包模板匹配阈值（比默认稍低，因为公共图片匹配度较低）
PACK_SERIES_CODES = ["A", "B"]  # 扩充包系列代号（仅用于切换次数控制）
PACK_AUTO_STRATEGIES = [
    "latest",
    "hrw_progress_balance",
    "hash_balance",  # 兼容旧配置
    "least_used",
]  # 自动选包策略
PACK_AUTO_EXCLUDE_SET_CODES = ["A4b"]  # 排除的限时系列
PACK_AUTO_HASH_VIRTUAL_NODES = 32  # 一致性哈希虚拟节点数

# 自动选包（hrw_progress_balance）权重参数
PACK_AUTO_HRW_TARGET_RARITIES = ["SR", "SAR"]  # 进度统计使用的目标稀有度
PACK_AUTO_HRW_PROGRESS_BETA = 4.0  # 进度缺口权重强度
PACK_AUTO_HRW_WEIGHT_MIN = 0.5  # 权重下限
PACK_AUTO_HRW_WEIGHT_MAX = 3.0  # 权重上限
PACK_AUTO_HRW_SEED = "rarity-gap-auto-39"  # HRW 稳定种子
PACK_AUTO_HRW_LOAD_EPSILON = 0.45  # 分配模拟容量松弛系数
PACK_AUTO_HRW_SEED_SCAN_COUNT = 300  # 分配模拟 seed 扫描次数

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
DEFAULT_OCR_LEVEL = "accurate"  # 默认 OCR 识别级别 ("fast" or "accurate")

# 游戏刷新时间配置（游戏固定 UTC 06:00 刷新；通过偏移换算本地刷新时刻）
GAME_UTC_OFFSET_HOURS = 8

# 调度配置
METADATA_DEFAULT_NODE_ID = "all"
METADATA_DEFAULT_SET_CODE = ""
METADATA_DEFAULT_PACK_NAME = ""
METADATA_DEFAULT_UI_STEP = 1

# 卡牌 Key 格式模板
CARD_KEY_FORMAT = "{set_code}-{number:03d}"

# 调度配置
DEFAULT_POLL_INTERVAL = 5.0  # 默认轮询间隔 (秒)
DEFAULT_MAX_WORKERS = 4  # 默认最大工作线程数
DEFAULT_TASK_GENERATION_INTERVAL = 60.0  # 默认任务生成间隔 (秒)

# 执行配置
DEFAULT_MAX_RETRIES = 3  # 默认最大重试次数
DEFAULT_RETRY_DELAY = 30.0  # 默认重试延迟 (秒)
DEFAULT_WAIT_AFTER_CLICK = 0.3  # 默认点击后等待时间 (秒)
DEFAULT_LONG_PRESS_STEPS = 600  # 默认长按步数（约 3 秒，0.005s/step）
DEFAULT_SWIPE_DURATION = 300  # 默认滑动持续时间 (毫秒)
SWIPE_DURATION_OPEN = 500  # 开包滑动持续时间 (毫秒)（1x速度）
# SWIPE_DURATION_OPEN = 300  # 开包滑动持续时间 (毫秒)（3x速度）
SWIPE_DURATION_REGISTER = 100  # 卡牌登录图鉴滑动持续时间 (毫秒)
DEFAULT_SCROLL_DURATION = 500  # 默认滚动持续时间 (毫秒)
DEFAULT_SCROLL_RATIO = 0.26  # 默认滚动距离占屏幕高度比例
DEFAULT_MAX_SCROLL_ATTEMPTS = 10  # 默认最大滚动尝试次数

# 滑动步数配置（相对 steps 模型）
SWIPE_STEPS_BASE_RATIO = 0.25  # 基准距离占屏幕高度比例
SWIPE_STEPS_BASE_VALUE = 8  # 基准距离对应步数
DEFAULT_SWIPE_STEPS = SWIPE_STEPS_BASE_VALUE  # 默认滑动步数（与 steps 语义一致）
SWIPE_STEPS_MIN = 6  # 步数下限
SWIPE_STEPS_MAX = 24  # 步数上限
SWIPE_STEPS_SCROLL = 10  # 通用列表滚动步数（对齐旧默认 500ms）
SWIPE_STEPS_OPEN = 10  # 开包滑动步数（对齐旧 500ms）
SWIPE_STEPS_REGISTER = 3  # 卡牌登录图鉴滑动步数（对齐旧 100ms）

# 数据库配置
DEFAULT_DB_NAME = "ptcgp_v2.db"  # 默认数据库文件名

# Web配置
DEFAULT_WEB_HOST = "127.0.0.1"
DEFAULT_WEB_PORT = 8000


# 模板缩放比例
# 注: 模板现在只裁剪不缩放(103x95)，比原来(513x473)小5倍
# 因此比例要放大5倍来补偿
# 最小包的比例，也就是扩展包列表页
SCALE_PACK_SERIES_SELECT = 1.15  # 旧值: 0.23
# 同系列选多个子包时的比例
SCALE_PACK_LIST = 4.1
# 点击开包前比例
SCALE_PACK_DETAIL = 5.1
# 游戏主页 比例
SCALE_PACK_HOME = 2.52
# 「pack_opening_select」 比例
SCALE_PACK_OPENING_SELECT = 4.46
# 「pack_opening_swipe」 比例
SCALE_PACK_OPENING_SWIPE = 7.32
# 「battle_series_select」 对战任务系列选择页面比例
# 调试确定：1.6（720p 下 Deluxe/Dialga/Mewtwo 等子包模板均能成功匹配，置信度 0.75+）
SCALE_BATTLE_SERIES_SELECT = 1.6
# 「battle_deck_select」 对战任务卡组列表页面沙漏图标比例
# 调试确定：0.85（置信度 0.9562）
SCALE_BATTLE_HOURGLASS = 0.85


# ========== YOLO + 感知哈希识别配置 ==========
# YOLO检测置信度阈值（来自 test_massive_matching.py 实测验证）
YOLO_OBB_THRESHOLD = 0.55
# Hash匹配相似度阈值（来自 test_massive_matching.py 实测验证）
HASH_SIMILARITY_THRESHOLD = 0.75
# Hash匹配相似度最小差距（用于排除相近候选，低于此值拒绝模糊匹配）
HASH_SIMILARITY_GAP_MIN = 0.02
# 系列优先级阈值：当最佳与次佳匹配差距小于此值时，优先选择系列号小的（如 A1 优先于 A4b）
HASH_SIMILARITY_TIE_THRESHOLD = 0.01

# 两阶段匹配配置
TOPK_CANDIDATES = 3  # 第一阶段候选数（原为20，优化为3）
SECOND_STAGE_STAGE1_WEIGHT = 0.4  # 第二阶段加权：stage1分数权重
SECOND_STAGE_STAGE2_WEIGHT = 0.6  # 第二阶段加权：stage2分数权重

# OBB检测优化
OBB_INSET_RATIO = 0.04  # OBB角点收缩比例（向内缩4%去除边缘噪声）

# 哈希裁剪比例（非对称裁剪，去除卡名等区域）
HASH_CROP_TOP_RATIO = 0.08  # 顶部裁剪8%（去除卡牌名称区域）
HASH_CROP_BOTTOM_RATIO = 0.03  # 底部裁剪3%
HASH_CROP_SIDE_RATIO = 0.03  # 左右各裁剪3%

# 多视角哈希变体（第二阶段使用不同顶部裁剪比例生成多个哈希）
DETECT_HASH_VARIANT_TOP_TRIMS = [0.0, 0.04, 0.08, 0.12]

# 高稀有度卡牌范围（用于记录账号卡牌）
HIGH_RARITY_TARGETS = ["RR", "AR", "SR", "SAR", "IM", "UR", "S", "SSR"]

# 通知状态配置
NOTIFICATION_TASK_STATUS_DEFAULTS = ["failed", "blocked", "timeout"]
NOTIFICATION_TASK_STATUS_OPTIONS = [
    "failed",
    "blocked",
    "timeout",
    "success",
]
