"""
教程模式页面配置

教程解锁模式专用的页面定义。
"""

PAGES_TUTORIAL = {
    # 玩法列表页面 - 新手教程列表
    "tutorial_list": {
        "identifiers": ["玩法"],
        "templates": ["wanfa_shalou"],
        "action": "handle_tutorial_list",
        "priority": 46,
        "exclude_identifiers": ["與他人對戰", "擴充組", "分級對戰", "對戰規則", "對戰課題"],
    },
    # 教程完成提示页面
    "tutorial_complete_hint": {
        "identifiers": ["若想知道更詳細的規則"],
        "action": "click_continue",
        "priority": 35,
    },
}
