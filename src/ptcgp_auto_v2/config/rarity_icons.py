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

# 唯一配置来源：rarity_code -> (template_name, count)
RARITY_CODE_REVERSE = {
    # diamond
    "C": ("diamond", 1),
    "U": ("diamond", 2),
    "R": ("diamond", 3),
    "RR": ("diamond", 4),
    # star
    "AR": ("star", 1),
    "SR": ("star", 2),
    "SAR": ("star", 2),
    "IM": ("star", 3),
    # shiny_star
    "S": ("shiny_star", 1),
    "SSR": ("shiny_star", 2),
    # crown
    "UR": ("crown", 1),
}
