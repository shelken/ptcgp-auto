"""
用户信息页面配置

用于获取用户信息的页面，在需要识别用户身份的模式中使用。
"""

PAGES_USER_INFO = {
    # 用户信息弹窗 - 提取用户名和朋友ID
    "user_info_popup": {
        "identifiers": ["您的玩家資訊"],
        "action": "extract_user_info",
        "priority": 5,
    },
    # 朋友列表页面 - 点击添加朋友图标
    "friends_list": {
        "identifiers": ["申請中", "朋友"],
        "match_all": True,  # 同时匹配避免误识别
        "action": "click_add_friends",
        "priority": 58,
    },
    # 社群页面 - 点击朋友标签
    "community_page": {
        "identifiers": ["他人的收藏", "朋友"],
        "match_all": True,  # 需要同时匹配，避免误识别
        "action": "click_friends_tab",
        "priority": 59,
        "exclude_identifiers": ["申請中"],  # 排除朋友列表页面
    },
    # 游戏主页 - 需要进入社群获取用户信息
    "game_home_main": {
        "identifiers": ["商店/兌換處", "得卡挑戰"],
        "match_all": True,
        "action": "handle_game_home",
        "priority": 60,
    },
    # 关闭按钮 - 退出弹窗
    "close_button": {
        "templates": ["btn_close"],
        "action": "click_template",
        "priority": 90,
    },
    # 返回按钮 - 回到上一页
    "back_button": {
        "templates": ["btn_back"],
        "action": "click_template",
        "priority": 91,
    },
}
