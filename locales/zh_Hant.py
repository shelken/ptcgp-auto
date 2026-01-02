"""
繁体中文语言配置
"""

# 等级列表（按此顺序遍历，可自定义顺序）
# 默认从精英开始到初级，这样可以先打高难度
BATTLE_LEVELS = ["精英", "高級", "中級", "初級"]

# 界面识别配置
# 每个界面定义：
#   - identifiers: 识别该界面的文字列表（任意一个匹配即可）
#   - action: 在该界面应该执行的动作
#   - priority: 优先级（数字越小优先级越高，用于多个界面都匹配时）
#   - exact_match: 是否精确匹配（默认 False，使用包含匹配）

PAGES = {
    # 弹窗 - 最高优先级（精确匹配，避免误匹配 POKéMON）
    "popup_ok": {
        "identifiers": ["OK", "確定", "确定"],
        "action": "click_identifier",
        "priority": 1,
        "exact_match": True,
    },
    # 战败提示弹窗 - 点击取消
    "battle_defeat_popup": {
        "identifiers": ["前往任務"],
        "action": "click_cancel",
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
        "action": "click_continue",
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
            "請將基礎寶可夢放置於戰鬥場",
            "你是先攻",
            "你是後攻",
            "對戰對手",
        ],
        "action": "wait",
        "priority": 20,
    },
    # 牌组详情页面 - 有对战按钮
    "deck_detail": {
        "identifiers": ["對戰！"],
        "action": "start_battle",
        "priority": 30,
    },
    # 扩充组选择页面（选择哪个卡包）
    "expansion_select": {
        "identifiers": ["選擇擴充組"],
        "action": "handle_expansion_select",
        "priority": 42,
    },
    # 牌组列表页面 - 在某个卡包内，有擴充組按钮可以进入扩充组
    "deck_list": {
        "identifiers": ["擴充組"],
        "templates": ["shalou"],
        "action": "handle_deck_list",
        "priority": 45,
        "exclude_identifiers": ["選擇擴充組"],
    },
    # 分级对战选择页面（等级选择）
    "ranked_battle_select": {
        "identifiers": ["分級對戰"],
        "action": "select_level",
        "priority": 50,
        "exclude_identifiers": ["擴充組"],
    },
    # 主对战菜单 - 需要点击单人对战
    "battle_menu": {
        "identifiers": ["與他人對戰"],
        "action": "click_solo_battle",
        "priority": 55,
    },
    # 单人对战主页（显示各种任务）
    "solo_battle_main": {
        "identifiers": ["單人對戰"],
        "action": "find_incomplete",
        "priority": 60,
        "exclude_identifiers": ["與他人對戰"],
    },
}

# 多语言文本映射（用于识别界面元素）
TEXT_VARIANTS = {
    "continue": [
        "點擊來繼續",
        "點擊以繼續",
        "點擊繼續",
        "繼續",
    ],
    "battle": [
        "對戰！",
        "對戰",
    ],
    "solo_battle": [
        "單人對戰",
    ],
    "ranked_battle": [
        "分級對戰",
    ],
    "elite_battle": [
        "精英對戰",
    ],
    "expansion": [
        "擴充包",
        "擴充組",
    ],
    "complete": [
        "Complete",
        "COMPLETE",
    ],
    "clear": [
        "CLEAR",
        "Clear",
    ],
    "auto": [
        "自動",
    ],
    "cancel": [
        "取消",
    ],
    "expansion_button": [
        "擴充組",
    ],
    "series_a": [
        "A系列",
    ],
    "series_b": [
        "B系列",
    ],
    "select_expansion": [
        "選擇擴充組",
    ],
    "series": [
        "系列",
    ],
}
