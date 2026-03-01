# -*- coding: utf-8 -*-
"""
卡牌匹配逻辑
"""
from typing import Optional, Tuple

from ptcgp_auto.recognizer_parts.template_matcher import _normalize_template_name
from ptcgp_auto import config

# 缩放扫描常量
MIN_TEMPLATE_SIZE = 16  # 缩放后模板最小边长（像素）
DEFAULT_MAX_SCALE = 3.0
DEFAULT_STEP = 0.02


def calc_valid_scale_range(
    template_shape, screen_shape, min_scale=0.1, max_scale=DEFAULT_MAX_SCALE
) -> Optional[Tuple[float, float]]:
    """
    计算有效的缩放范围
    """
    orig_h, orig_w = template_shape[:2]
    screen_h, screen_w = screen_shape[:2]

    # 计算最小有效缩放比例
    min_valid_scale = max(
        min_scale,
        MIN_TEMPLATE_SIZE / orig_w,
        MIN_TEMPLATE_SIZE / orig_h,
    )
    # 向上取整到 0.02
    min_valid_scale = round(min_valid_scale + 0.01, 2)

    # 计算最大有效缩放比例
    max_valid_scale = min(max_scale, screen_w / orig_w, screen_h / orig_h)

    if min_valid_scale > max_valid_scale:
        return None

    return (min_valid_scale, max_valid_scale)


def scan_best_scale(
    recognizer,
    img,
    template_name,
    min_scale=0.1,
    max_scale=DEFAULT_MAX_SCALE,
    step=DEFAULT_STEP,
) -> Tuple[float, float]:
    """扫描所有缩放比例，返回最佳匹配的 (scale, confidence)"""
    best_scale = 1.0
    best_confidence = 0.0

    # 获取模板
    template_key = _normalize_template_name(template_name)
    template = recognizer.templates.get(template_key)
    if template is None:
        return best_scale, best_confidence

    orig_h, orig_w = template.shape[:2]

    # 获取截图尺寸
    screen = recognizer.pil_to_cv2(img)

    # 计算有效缩放范围
    scale_range = calc_valid_scale_range(
        template.shape, screen.shape, min_scale, max_scale
    )
    if scale_range is None:
        print(f"WARNING: 模板尺寸 {orig_w}x{orig_h} 无有效缩放范围")
        return best_scale, best_confidence

    min_valid_scale, max_valid_scale = scale_range
    num_steps = int((max_valid_scale - min_valid_scale) / step) + 1
    print(
        f"  范围 {min_valid_scale:.2f}-{max_valid_scale:.2f} "
        f"(模板 {orig_w}x{orig_h}，步进 {step}，共 {num_steps} 步)"
    )

    # 生成缩放比例列表并逐一测试
    scale = min_valid_scale
    while scale <= max_valid_scale + 0.001:  # 浮点数精度处理
        current_scale = round(scale, 2)
        confidence = recognizer.get_template_confidence_at_scale(
            img, template_name, current_scale
        )
        if confidence > best_confidence:
            best_confidence = confidence
            best_scale = current_scale
        scale += step

    return best_scale, best_confidence
