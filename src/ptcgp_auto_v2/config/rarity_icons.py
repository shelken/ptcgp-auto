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

# 唯一配置来源：rarity_code -> 图标参数 + 展示文案
RARITY_META = {
    # diamond
    "C": {
        "template": "diamond",
        "count": 1,
        "display_zh": "C (1钻)",
        "display_en": "C (1 Diamond)",
    },
    "U": {
        "template": "diamond",
        "count": 2,
        "display_zh": "U (2钻)",
        "display_en": "U (2 Diamonds)",
    },
    "R": {
        "template": "diamond",
        "count": 3,
        "display_zh": "R (3钻)",
        "display_en": "R (3 Diamonds)",
    },
    "RR": {
        "template": "diamond",
        "count": 4,
        "display_zh": "RR (4钻)",
        "display_en": "RR (4 Diamonds)",
    },
    # star
    "AR": {
        "template": "star",
        "count": 1,
        "display_zh": "AR (1星)",
        "display_en": "AR (1 Star)",
    },
    "SR": {
        "template": "star",
        "count": 2,
        "display_zh": "SR (2星)",
        "display_en": "SR (2 Stars)",
    },
    "SAR": {
        "template": "star",
        "count": 2,
        "display_zh": "SAR (2星)",
        "display_en": "SAR (2 Stars)",
    },
    "IM": {
        "template": "star",
        "count": 3,
        "display_zh": "IM (3星)",
        "display_en": "IM (3 Stars)",
    },
    # shiny_star
    "S": {
        "template": "shiny_star",
        "count": 1,
        "display_zh": "S (异色)",
        "display_en": "S (Shiny)",
    },
    "SSR": {
        "template": "shiny_star",
        "count": 2,
        "display_zh": "SSR (异色SSR)",
        "display_en": "SSR (Shiny SSR)",
    },
    # crown
    "UR": {
        "template": "crown",
        "count": 1,
        "display_zh": "UR (皇冠)",
        "display_en": "UR (Crown)",
    },
}


# 兼容旧接口：rarity_code -> (template_name, count)
RARITY_CODE_REVERSE = {
    code: (meta["template"], meta["count"]) for code, meta in RARITY_META.items()
}


def get_rarity_display(rarity_code: str, lang: str = "zh_CN") -> str:
    """获取稀有度展示文案。"""
    meta = RARITY_META.get(rarity_code)
    if not meta:
        return rarity_code
    key = "display_zh" if lang.lower().startswith("zh") else "display_en"
    return str(meta.get(key, rarity_code))
