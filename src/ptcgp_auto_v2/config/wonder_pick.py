# -*- coding: utf-8 -*-
"""
得卡挑战配置
"""

# 稀有度优先级（高 -> 低）
WONDER_PICK_RARITY_PRIORITY = ["SAR", "SR", "AR", "RR", "R", "U", "C"]

# 稀有度对应挑战力消耗
WONDER_PICK_RARITY_COSTS = {
    "C": 1,
    "U": 1,
    "R": 2,
    "RR": 3,
    "AR": 3,
    "SR": 4,
    "SAR": 4,
}

# 选卡位置索引 -> 可点击位置索引列表
WONDER_PICK_RULES = {
    1: [2, 4],
    2: [2, 4, 5],
    3: [3, 5],
    4: [1, 5],
    5: [2, 3, 5],
}

# 基于 1080x1920 的五个点击点位（上三下二）
WONDER_PICK_POSITIONS = {
    1: (200, 720),
    2: (540, 720),
    3: (880, 720),
    4: (365, 1200),
    5: (715, 1200),
}

# 默认目标稀有度 只要 两星
WONDER_PICK_DEFAULT_TARGETS = ["SAR", "SR"]
