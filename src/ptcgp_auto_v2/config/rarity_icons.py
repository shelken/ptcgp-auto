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

# 唯一配置来源：rarity_code -> 图标参数 + 展示文案 + 优先级 + 得卡挑战消耗 + 交换配置
RARITY_META = {
    # diamond: priority 低 -> 高, wonder_pick_cost 递增
    "C": {
        "template": "diamond",
        "count": 1,
        "display_zh": "C (1钻)",
        "display_en": "C (1 Diamond)",
        "priority": 1,
        "wonder_pick_cost": 1,
        "exchange_cost": 0,
        "exchangeable": True,
    },
    "U": {
        "template": "diamond",
        "count": 2,
        "display_zh": "U (2钻)",
        "display_en": "U (2 Diamonds)",
        "priority": 2,
        "wonder_pick_cost": 1,
        "exchange_cost": 0,
        "exchangeable": True,
    },
    "R": {
        "template": "diamond",
        "count": 3,
        "display_zh": "R (3钻)",
        "display_en": "R (3 Diamonds)",
        "priority": 3,
        "wonder_pick_cost": 2,
        "exchange_cost": 1200,
        "exchangeable": True,
    },
    "RR": {
        "template": "diamond",
        "count": 4,
        "display_zh": "RR (4钻)",
        "display_en": "RR (4 Diamonds)",
        "priority": 4,
        "wonder_pick_cost": 3,
        "exchange_cost": 5000,
        "exchangeable": True,
    },
    # star
    "AR": {
        "template": "star",
        "count": 1,
        "display_zh": "AR (1星)",
        "display_en": "AR (1 Star)",
        "priority": 5,
        "wonder_pick_cost": 3,
        "exchange_cost": 4000,
        "exchangeable": True,
    },
    "SR": {
        "template": "star",
        "count": 2,
        "display_zh": "SR (2星)",
        "display_en": "SR (2 Stars)",
        "priority": 6,
        "wonder_pick_cost": 4,
        "exchange_cost": 25000,
        "exchangeable": True,
    },
    "SAR": {
        "template": "star",
        "count": 2,
        "display_zh": "SAR (2星)",
        "display_en": "SAR (2 Stars)",
        "priority": 7,
        "wonder_pick_cost": 4,
        "exchange_cost": 25000,
        "exchangeable": True,
    },
    "IM": {
        "template": "star",
        "count": 3,
        "display_zh": "IM (3星)",
        "display_en": "IM (3 Stars)",
        "priority": 8,
        "exchange_cost": None,
        "exchangeable": False,
    },
    # shiny_star
    "S": {
        "template": "shiny_star",
        "count": 1,
        "display_zh": "S (异色)",
        "display_en": "S (Shiny)",
        "priority": 9,
        "exchange_cost": 10000,
        "exchangeable": True,
    },
    "SSR": {
        "template": "shiny_star",
        "count": 2,
        "display_zh": "SSR (异色SSR)",
        "display_en": "SSR (Shiny SSR)",
        "priority": 10,
        "exchange_cost": 30000,
        "exchangeable": True,
    },
    # crown
    "UR": {
        "template": "crown",
        "count": 1,
        "display_zh": "UR (皇冠)",
        "display_en": "UR (Crown)",
        "priority": 11,
        "exchange_cost": None,
        "exchangeable": False,
    },
}

# 兼容旧接口：rarity_code -> (template_name, count)
RARITY_CODE_REVERSE = {
    code: (meta["template"], meta["count"]) for code, meta in RARITY_META.items()
}


def get_rarity_display(rarity_code: str, lang: str | None = None) -> str:
    """获取稀有度展示文案。"""
    from ptcgp_auto_v2.config.lang import DEFAULT_LANG_KEY

    if not lang:
        lang = DEFAULT_LANG_KEY
    meta = RARITY_META.get(rarity_code)
    if not meta:
        return rarity_code
    key = "display_zh" if lang.lower().startswith("zh") else "display_en"
    return str(meta.get(key, rarity_code))
