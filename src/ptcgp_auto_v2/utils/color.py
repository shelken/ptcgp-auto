# -*- coding: utf-8 -*-
"""
颜色检测工具

用于检测 UI 元素的状态（如按钮是否可点击）。
"""

import logging
from typing import Tuple

import cv2
import numpy as np
from PIL import Image

logger = logging.getLogger(__name__)

# ============================================================
# 预定义颜色范围 (HSV)
# OpenCV 中 H: 0-179, S: 0-255, V: 0-255
# ============================================================
COLORS = {
    "green": {"lower": (35, 80, 80), "upper": (100, 255, 255)},
    "gray": {"lower": (0, 0, 60), "upper": (180, 30, 200)},
}


def check_color_ratio(
    screenshot: Image.Image,
    region: Tuple[int, int, int, int],
    color_name: str,
    threshold: float = 0.1,
) -> bool:
    """
    检测区域内指定颜色占比是否超过阈值

    Args:
        screenshot: PIL Image 截图
        region: (x1, y1, x2, y2) 检测区域
        color_name: 颜色名称（green/gray）
        threshold: 颜色占比阈值

    Returns:
        True 如果颜色占比超过阈值
    """
    if color_name not in COLORS:
        logger.warning(f"未知的颜色名称: {color_name}")
        return False

    color_config = COLORS[color_name]
    x1, y1, x2, y2 = region

    # PIL -> OpenCV (BGR)
    img = cv2.cvtColor(np.array(screenshot), cv2.COLOR_RGB2BGR)
    height, width = img.shape[:2]

    # 边界检查
    x1, y1 = max(0, x1), max(0, y1)
    x2, y2 = min(width, x2), min(height, y2)

    if x2 <= x1 or y2 <= y1:
        logger.debug(f"[颜色] 无效区域: ({x1},{y1})-({x2},{y2})")
        return False

    roi = img[y1:y2, x1:x2]
    hsv = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)
    mask = cv2.inRange(
        hsv,
        np.array(color_config["lower"]),
        np.array(color_config["upper"]),
    )
    ratio = np.count_nonzero(mask) / mask.size

    logger.debug(
        f"[颜色] 区域({x1},{y1})-({x2},{y2}) {color_name}占比={ratio:.2%} 阈值={threshold:.2%}"
    )

    return ratio >= threshold


def is_button_clickable(
    screenshot: Image.Image,
    box: Tuple[int, int, int, int],
    threshold: float = 0.1,
) -> bool:
    """
    检测按钮是否可点击（绿色状态）

    Args:
        screenshot: PIL Image 截图
        box: 按钮的 OCR box (x1, y1, x2, y2)
        threshold: 绿色占比阈值

    Returns:
        True 如果按钮是绿色（可点击）
    """
    return check_color_ratio(screenshot, box, "green", threshold)
