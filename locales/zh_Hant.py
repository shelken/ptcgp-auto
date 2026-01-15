"""
繁体中文语言配置
"""

# 等级列表（按此顺序遍历，可自定义顺序）
# 默认从精英开始到初级，这样可以先打高难度
BATTLE_LEVELS = ["精英", "高級", "中級", "初級"]

# 牌组关键词（用于从标题提取卡包名）
# 格式如: "毽子花牌組（高級擴充包ex）"
DECK_KEYWORD = "牌組"

# 系列列表（按此顺序遍历）
SERIES = ["A", "B"]

# 界面识别配置
# 每个界面定义：
#   - identifiers: 识别该界面的文字列表（任意一个匹配即可）
#   - action: 在该界面应该执行的动作
#   - priority: 优先级（数字越小优先级越高，用于多个界面都匹配时）
#   - exact_match: 是否精确匹配（默认 False，使用包含匹配）

PAGES = {
    # 弹窗 - 最高优先级（精确匹配，避免误匹配 POKéMON）
    "popup_ok": {
        "identifiers": ["OK"],
        "action": "click_identifier",
        "priority": 1,
        "exact_match": True,
    },
    # 网络错误弹窗 - 点击重试
    "network_error_popup": {
        "identifiers": ["再試一次"],
        "action": "click_identifier",
        "priority": 1,
        "exact_match": True,
    },
    # 战败提示弹窗 - 点击取消
    "battle_defeat_popup": {
        "identifiers": ["前往任務"],
        "action": "click_cancel",
        "priority": 2,
        "exact_match": True,
    },
    # 对战结果页面 - 需要点击继续
    "battle_result_continue": {
        "identifiers": ["點擊來繼續", "點擊以繼續"],
        "action": "click_identifier",
        "priority": 10,
        "exact_match": True,
    },
    # 继续按钮
    "continue_button": {
        "identifiers": ["繼續"],
        "action": "click_identifier",
        "priority": 11,
        "exact_match": True,
    },
    "continue_battle": {
        "identifiers": ["是", "要繼續上次中斷的對戰嗎？"],
        "action": "click_identifier",
        "priority": 11,
        "match_all": True,
    },
    # 对战记录页面
    "battle_record": {
        "identifiers": ["對戰紀錄"],
        "action": "click_continue",
        "priority": 15,
        "exact_match": True,
    },
    # 经验值结算页面
    "exp_result": {
        "identifiers": ["玩家經驗值"],
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
        "action": "wait_battle",
        "priority": 20,
    },
    # 牌组详情页面 - 有对战按钮
    "deck_detail": {
        "identifiers": ["對戰！"],
        "action": "start_battle",
        "priority": 30,
        "exact_match": True,
    },
    # 扩充组选择页面（选择哪个卡包）
    "expansion_select": {
        "identifiers": ["選擇擴充組"],
        "action": "handle_expansion_select",
        "priority": 42,
    },
    # 牌组列表页面 - 在某个卡包内，有擴充組按钮可以进入扩充组
    # 注意：不要求 shalou 模板，因为沙漏只在有未完成牌组时出现
    # 沙漏检测在 handle_deck_list 动作内部进行
    "deck_list": {
        "identifiers": ["擴充組"],
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
    # 对战菜单（锁定状态）- 新手账号单人对战被锁，需要完成教程
    "battle_menu_locked": {
        "identifiers": ["與他人對戰"],
        "templates": ["icon_lock"],
        "match_all": True,
        "action": "handle_tutorial_unlock",
        "priority": 54,
    },
    # 玩法列表页面 - 新手教程列表
    # 注意：优先级低于 deck_list(45)，避免底部导航"玩法"误匹配
    "tutorial_list": {
        "identifiers": ["玩法"],
        "templates": ["wanfa_shalou"],
        "action": "handle_tutorial_list",
        "priority": 46,
        "exclude_identifiers": ["與他人對戰", "擴充組", "分級對戰"],
    },
    # 教学界面（后续完善）
    # "tutorial_teaching": {
    #     "templates": ["hand_pointer"],
    #     "action": "handle_tutorial_step",
    #     "priority": 35,
    # },
    # 单人对战主页（显示各种任务）
    "solo_battle_main": {
        "identifiers": ["單人對戰"],
        "action": "find_incomplete",
        "priority": 60,
        "exclude_identifiers": ["與他人對戰"],
    },
    # TODO for ENG 游戏主页
    "game_home_main": {
        "identifiers": ["商店/兌換處", "得卡挑戰"],
        "match_all": True,
        "action": "click_template",
        "action_template": "icon_battle",
        "priority": 60,
    },
    # TODO for ENG 开启页面
    "game_open_page": {
        "identifiers": ["點擊畫面開始遊戲"],
        "action": "click_identifier",
        "priority": 60,
    },
    # TODO for ENG 各种原因跳到主页了
    "_main_page": {
        "identifiers": ["Pokémon Trad", "搜索游戏和应用"],
        "match_all": True,
        "action": "click_identifier",
        "priority": 100,
    },
}

# 辅助文本模式（供 actions 模块查询）
TEXT_PATTERNS = {
    "auto": ["自動"],
    "series": {
        "A": ["A系列"],
        "B": ["B系列"],
    },
    "skip_titles": ["選擇擴充組", "系列"],
    "no_battles": ["沒有可挑戰的對戰"],
    "cancel": ["取消"],
    "expansion_button": ["擴充組"],
    "ranked_battle": ["分級對戰"],
    "solo_battle": ["單人對戰"],
}
