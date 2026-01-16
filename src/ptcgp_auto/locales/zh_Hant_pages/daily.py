"""
每日开包模式页面配置

每日免费开包模式专用的页面定义。
待使用 debug tool 探索后补充。
"""

PAGES_DAILY = {
    # 游戏主页 - 开包模式入口
    "game_home_main": {
        "identifiers": ["商店/兌換處", "得卡挑戰"],
        "match_all": True,
        "action": "click_pack_icon",  # 开包模式：点击开包图标
        "priority": 60,
    },
    # TODO: 以下页面待探索后补充
    # "pack_series_select": {...},  # 系列选择页面
    # "pack_list": {...},           # 卡包列表页面
    # "pack_opening": {...},        # 开包动画页面
}
