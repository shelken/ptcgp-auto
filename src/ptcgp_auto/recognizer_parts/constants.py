"""
识别器常量配置
"""

# 预定义颜色范围 (HSV)
# OpenCV 中 H: 0-179, S: 0-255, V: 0-255
COLORS = {
    "green": {"lower": (35, 80, 80), "upper": (100, 255, 255)},  # 扩展到青绿色
    "gray": {"lower": (0, 0, 60), "upper": (180, 30, 200)},
    "red": {"lower": (0, 80, 80), "upper": (10, 255, 255)},  # 红色有两段
    "red2": {"lower": (160, 80, 80), "upper": (179, 255, 255)},
    "blue": {"lower": (100, 80, 80), "upper": (130, 255, 255)},
    "yellow": {"lower": (20, 80, 80), "upper": (35, 255, 255)},
}

# 颜色状态检测配置
# 用于检测 UI 元素的开关/选中状态
COLOR_STATES = {
    "auto_battle": {
        "locator": {
            "type": "text_pattern",  # text_pattern 或 template
            "key": "auto",  # TEXT_PATTERNS 的 key
        },
        "color_region": {
            "position": "left",  # left / right / above / below
            "offset": 0.01,  # 相对于屏幕宽度/高度的比例
            "width": 0.05,  # 区域宽度（屏幕宽度比例）
            "height": 0.03,  # 区域高度（屏幕高度比例）
        },
        "color": "green",  # COLORS 中的预定义颜色名
        "threshold": 0.04,  # 颜色占比阈值（4.6% > 4%）
    },
}
