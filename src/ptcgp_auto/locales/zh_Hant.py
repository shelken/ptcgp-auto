"""
繁体中文语言配置
"""

# 导入页面配置模块
from . import zh_Hant_pages as pages

# 等级列表（按此顺序遍历，可自定义顺序）
# 默认从精英开始到初级，这样可以先打高难度
BATTLE_LEVELS = ["精英", "高級", "中級", "初級"]

# 牌组关键词（用于从标题提取卡包名）
# 格式如: "毽子花牌組（高級擴充包ex）"
DECK_KEYWORD = "牌組"

# 系列列表（按此顺序遍历）
SERIES = ["A", "B"]

# 模式配置：定义每个模式包含哪些页面组
MODES = {
    "tutorial": ["common", "tutorial"],
    "battle": ["common", "user_info", "battle", "tutorial"],
}

# 辅助文本模式（供 actions 模块查询）
TEXT_PATTERNS = {
    "auto": ["自動"],
    "series": {
        "A": ["A系列"],
        "B": ["B系列"],
    },
    "series_keyword": ["系列"],
    "skip_titles": ["選擇擴充組", "系列"],
    "no_battles": ["沒有可挑戰的對戰"],
    "cancel": ["取消"],
    "expansion_button": ["擴充組"],
    "ranked_battle": ["分級對戰"],
    "solo_battle": ["單人對戰"],
    "first_clear_reward": ["首次過關報酬"],
    # 开包相关
    "open_pack_1": ["開封1包"],
    "open_pack": ["開封"],
    "continue": ["繼續"],
    "close_button": ["×"],
    "long_press": ["長按", "長按以跳過", "長按開封", "長投"], # 540p情况出现ocr结果开始有问题，长投
}
