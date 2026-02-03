# -*- coding: utf-8 -*-
"""
稀有度图标配置（基于 1080x1920 基准像素）

注意：实际像素需通过 adb.scaled_x / adb.scaled_y 进行缩放。
"""

# 模板路径（相对 templates/）
RARITY_ICON_TEMPLATES = {
    "diamond": "icon_diamond.png",
    "star": "icon_star.png",
    "shiny_star": "icon_shiny_star.png",
    "crown": "icon_crown.png",
}

# 分组参数（基于 1080x1920）
RARITY_GROUP_DEFAULTS = {
    "threshold": 0.8,
    "nms_iou": 0.3,
    "row_tol_px": 24,
    "gap_px": 60,
    "min_count": 1,
}

# 正向映射：检测结果 -> rarity_code
RARITY_CODE_MAP = {
    ("diamond", 1): "C",
    ("diamond", 2): "U",
    ("diamond", 3): "R",
    ("diamond", 4): "RR",
    ("star", 1): "AR",
    ("star", 2): "SR",
    ("star", 3): "IM",
    ("shiny_star", 1): "S",
    ("shiny_star", 2): "SSR",
    ("crown", 1): "UR",
}

# 反向映射：rarity_code -> (template_name, count)
RARITY_CODE_REVERSE = {
    "SR": ("star", 2),
    "SAR": ("star", 2),
    "IM": ("star", 3),
    "UR": ("crown", 1),
    "SSR": ("shiny_star", 2),
}
