"""
通用页面配置 - 所有模式共享

这些页面在所有模式（对战、教程、开包）中都会使用。
"""

PAGES_COMMON = {
    # OK 弹窗
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
    # 继续按钮
    "continue_button": {
        "identifiers": ["繼續"],
        "action": "click_identifier",
        "priority": 11,
        "exact_match": True,
    },
    # 游戏开启页面
    "game_open_page": {
        "identifiers": ["點擊畫面開始遊戲"],
        "action": "click_identifier",
        "priority": 60,
    },
    # 模拟器主页
    "_main_page": {
        "identifiers": ["Pokémon Trad", "搜索游戏和应用"],
        "match_all": True,
        "action": "click_identifier",
        "exclude_identifiers": ["关闭应用"],
        "priority": 100,
    },
    # 关闭应用弹窗
    "_close_app_popup": {
        "identifiers": ["关闭应用", "应用信息"],
        "match_all": True,
        "action": "click_identifier",
        "priority": 99,
    },
}
