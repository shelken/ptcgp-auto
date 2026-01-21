"""
对战模式页面配置

自动对战模式专用的页面定义。
"""

PAGES_BATTLE = {
    # 游戏主页 - 对战模式入口
    "game_home_main": {
        "identifiers": ["商店/兌換處", "得卡挑戰"],
        "match_all": True,
        "action": "handle_game_home",
        "priority": 60,
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
    # 继续对战确认
    "continue_battle": {
        "identifiers": ["是", "要繼續上次中斷的對戰嗎？"],
        "action": "click_identifier",
        "priority": 11,
        "match_all": True,
    },
    # 对战记录页面
    "battle_record": {
        "identifiers": ["對戰紀錄"],
        "action": "tap_screen_center",
        "priority": 15,
        "exact_match": True,
    },
    # 经验值结算页面
    "exp_result": {
        "identifiers": ["玩家經驗值"],
        "action": "tap_screen_center",
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
        "identifiers": ["對戰！", "首次過關報酬"],
        "action": "start_battle",
        "priority": 30,
    },
    # 扩充组选择页面
    "expansion_select": {
        "identifiers": ["選擇擴充組"],
        "action": "handle_expansion_select",
        "priority": 42,
    },
    # 牌组列表页面
    "deck_list": {
        "identifiers": ["擴充組"],
        "action": "handle_deck_list",
        "priority": 45,
        "exclude_identifiers": ["選擇擴充組"],
    },
    # 分级对战选择页面
    "ranked_battle_select": {
        "identifiers": ["分級對戰"],
        "action": "select_level",
        "priority": 50,
        "exclude_identifiers": ["擴充組"],
    },
    # 主对战菜单
    "battle_menu": {
        "identifiers": ["與他人對戰"],
        "action": "click_solo_battle",
        "priority": 55,
    },
    # 对战菜单（锁定状态）
    "battle_menu_locked": {
        "identifiers": ["與他人對戰"],
        "templates": ["icon_lock"],
        "match_all": True,
        "action": "handle_tutorial_unlock",
        "priority": 54,
    },
    # 单人对战主页
    "solo_battle_main": {
        "identifiers": ["單人對戰"],
        "action": "find_incomplete",
        "priority": 60,
        "exclude_identifiers": ["與他人對戰"],
    },
    # 开包页面 - 对战模式下返回
    "game_show_pack": {
        "identifiers": ["提供比例", "其他擴充包"],
        "match_all": True,
        "action": "go_back",
        "priority": 60,
    },
}
