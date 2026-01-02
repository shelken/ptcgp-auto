"""
PTCGP 自动化脚本配置
"""

# ADB 连接配置
ADB_HOST = "127.0.0.1"
ADB_PORT = 5555  # BlueStacks Air 默认端口，可能需要根据实际情况调整

# 等待时间配置（秒）
WAIT_AFTER_CLICK = 0.5  # 点击后等待
WAIT_PAGE_TRANSITION = 1.5  # 页面切换等待
WAIT_BATTLE_CHECK_INTERVAL = 10  # 对局中检测间隔（默认10秒）
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

# 等级列表（按此顺序遍历，可自定义顺序）
# 默认从精英开始到初级，这样可以先打高难度
BATTLE_LEVELS = ["精英", "高級", "中級", "初級"]

# ==================== 界面识别配置 ====================
# 每个界面定义：
#   - identifiers: 识别该界面的文字列表（任意一个匹配即可）
#   - action: 在该界面应该执行的动作
#   - priority: 优先级（数字越小优先级越高，用于多个界面都匹配时）
#   - exact_match: 是否精确匹配（默认 False，使用包含匹配）

PAGES = {
    # 弹窗 - 最高优先级（精确匹配，避免误匹配 POKéMON）
    "popup_ok": {
        "identifiers": ["OK", "確定", "确定"],
        "action": "click_identifier",  # 点击识别到的文字
        "priority": 1,
        "exact_match": True,  # 必须精确匹配
    },

    # 战败提示弹窗 - 点击取消
    "battle_defeat_popup": {
        "identifiers": ["前往任務"],
        "action": "click_cancel",  # 点击取消按钮
        "priority": 2,
    },

    # 对战结果页面 - 需要点击继续
    "battle_result_continue": {
        "identifiers": ["點擊來繼續", "點擊以繼續", "點擊繼續", "Tap to continue"],
        "action": "click_identifier",
        "priority": 10,
    },

    # 继续按钮
    "continue_button": {
        "identifiers": ["繼續"],
        "action": "click_identifier",
        "priority": 11,
    },

    # 对战记录页面
    "battle_record": {
        "identifiers": ["對戰紀錄"],
        "action": "click_continue",  # 点击屏幕继续
        "priority": 15,
    },

    # 经验值结算页面
    "exp_result": {
        "identifiers": ["玩家經驗值", "EXP"],
        "action": "click_continue",
        "priority": 16,
    },

    # 对战中 - 等待
    "battle_in_progress": {
        "identifiers": [
            "請將基礎寶可夢放置於戰鬥場",  # 开始时
            "你是先攻",
            "你是後攻",
            "對戰對手",  # 对战中顶部显示
        ],
        "action": "wait",  # 等待对战结束
        "priority": 20,
    },

    # 牌组详情页面 - 有对战按钮
    "deck_detail": {
        "identifiers": ["對戰！"],
        "action": "start_battle",  # 开启自动并点击对战
        "priority": 30,
    },

    # 扩充组选择页面（选择哪个卡包）
    "expansion_select": {
        "identifiers": ["選擇擴充組"],
        "action": "handle_expansion_select",  # 选择未完成的卡包
        "priority": 42,
    },

    # 牌组列表页面 - 在某个卡包内，有擴充組按钮可以进入扩充组
    "deck_list": {
        "identifiers": ["擴充組"],  # 牌组列表页面有这个按钮
        "templates": ["shalou"],  # 沙漏图标
        "action": "handle_deck_list",  # 处理牌组列表
        "priority": 45,
        "exclude_identifiers": ["選擇擴充組"],  # 排除扩充组选择页面
    },

    # 分级对战选择页面（等级选择）
    "ranked_battle_select": {
        "identifiers": ["分級對戰"],
        "action": "select_level",  # 选择未完成的等级
        "priority": 50,
        "exclude_identifiers": ["擴充組"],  # 排除牌组列表页面
    },

    # 主对战菜单 - 需要点击单人对战
    "battle_menu": {
        "identifiers": ["與他人對戰"],  # 只有主菜单有这个
        "action": "click_solo_battle",  # 点击单人对战入口
        "priority": 55,
    },

    # 单人对战主页（显示各种任务）
    "solo_battle_main": {
        "identifiers": ["單人對戰"],
        "action": "find_incomplete",  # 寻找未完成的任务
        "priority": 60,
        "exclude_identifiers": ["與他人對戰"],  # 排除主菜单
    },
}

# 多语言文本映射（用于识别界面元素）
# 每个键对应一个功能，值是可能出现的所有文本变体
TEXT_VARIANTS = {
    # 继续按钮的各种形式
    "continue": [
        "點擊來繼續",
        "點擊以繼續",
        "點擊繼續",
        "繼續",
        "Tap to continue",
        "Continue",
        "TAP TO CONTINUE",
    ],
    # 对战按钮
    "battle": [
        "對戰！",  # 带感叹号的优先匹配
        "對戰",
        "Battle!",
        "Battle",
        "BATTLE",
    ],
    # 单人对战
    "solo_battle": [
        "單人對戰",
        "Solo Battle",
    ],
    # 分级对战（等级选择界面的标题）
    "ranked_battle": [
        "分級對戰",
        "Ranked Battle",
    ],
    # 精英对战
    "elite_battle": [
        "精英對戰",
        "Elite Battle",
    ],
    # 扩充组/扩充包
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
