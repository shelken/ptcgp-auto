"""
PTCGP 自动化脚本配置
"""

# ADB 连接配置
ADB_HOST = "127.0.0.1"
ADB_PORT = 5555  # BlueStacks Air 默认端口，可能需要根据实际情况调整

# 等待时间配置（秒）
WAIT_AFTER_CLICK = 0.5  # 点击后等待
WAIT_PAGE_TRANSITION = 1.5  # 页面切换等待
WAIT_BATTLE_CHECK_INTERVAL = 5  # 对局中检测间隔
WAIT_BATTLE_TIMEOUT = 300  # 对局超时时间（5分钟）

# 屏幕分辨率（BlueStacks 默认）
SCREEN_WIDTH = 1080
SCREEN_HEIGHT = 1920

# OCR 配置 (Apple Vision Framework)
# Vision Framework 原生支持 Apple Silicon 硬件加速，无需额外配置
OCR_RECOGNITION_LEVEL = "accurate"  # "accurate" 或 "fast"
OCR_LANGUAGES = ["zh-Hant", "en-US"]  # 繁体中文 + 英文

# 模板匹配阈值（0-1，越高越严格）
TEMPLATE_THRESHOLD = 0.8

# 等级列表（按顺序遍历，繁体中文）
BATTLE_LEVELS = ["初級", "中級", "高級", "菁英"]

# 多语言文本映射（用于识别界面元素）
# 每个键对应一个功能，值是可能出现的所有文本变体
TEXT_VARIANTS = {
    # 继续按钮的各种形式
    "continue": [
        "點擊以繼續",
        "點擊繼續",
        "繼續",
        "Tap to continue",
        "Continue",
        "TAP TO CONTINUE",
    ],
    # 对战按钮
    "battle": [
        "對戰",
        "Battle",
        "BATTLE",
    ],
    # 单人对战
    "solo_battle": [
        "單人對戰",
        "Solo Battle",
    ],
    # 扩充组
    "expansion": [
        "擴充包",
        "擴充組",
        "Expansion",
    ],
    # 完成状态
    "complete": [
        "Complete",
        "COMPLETE",
    ],
    # 通关状态
    "clear": [
        "CLEAR",
        "Clear",
    ],
    # 自动模式
    "auto": [
        "自動",
        "Auto",
        "AUTO",
    ],
}

# 调试模式
DEBUG = True  # 开启后会保存截图和识别结果
DEBUG_DIR = "debug_output"
