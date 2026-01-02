"""
PTCGP 自动化脚本配置
"""

# ADB 连接配置
ADB_HOST = "127.0.0.1"
ADB_PORT = 5555  # BlueStacks Air 默认端口，可能需要根据实际情况调整

# 等待时间配置（秒）
WAIT_AFTER_CLICK = 0.5          # 点击后等待
WAIT_PAGE_TRANSITION = 1.5      # 页面切换等待
WAIT_BATTLE_CHECK_INTERVAL = 5  # 对局中检测间隔
WAIT_BATTLE_TIMEOUT = 300       # 对局超时时间（5分钟）

# 屏幕分辨率（BlueStacks 默认）
SCREEN_WIDTH = 1080
SCREEN_HEIGHT = 1920

# OCR 配置
OCR_LANGUAGES = ['en', 'ch_sim']  # 英文 + 简体中文

# 模板匹配阈值（0-1，越高越严格）
TEMPLATE_THRESHOLD = 0.8

# 等级列表（按顺序遍历）
BATTLE_LEVELS = ['初级', '中级', '高级', '精英']

# 调试模式
DEBUG = True  # 开启后会保存截图和识别结果
DEBUG_DIR = "debug_output"
