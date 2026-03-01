# -*- coding: utf-8 -*-
"""
模板缩放扫描工具

提供自动扫描最佳缩放比例的功能。
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from typing import Optional, Tuple
    from PIL import Image
    from ptcgp_auto_v2.infra.template import TemplateMatcher


# 缩放扫描常量
MIN_TEMPLATE_SIZE = 16  # 缩放后模板最小边长（像素）
DEFAULT_MAX_SCALE = 3.0
DEFAULT_STEP = 0.02


def calc_valid_scale_range(
    template_shape: tuple,
    screen_shape: tuple,
    min_scale: float = 0.1,
    max_scale: float = DEFAULT_MAX_SCALE,
) -> Optional[Tuple[float, float]]:
    """
    计算有效的缩放范围

    Args:
        template_shape: (height, width, channels) 模板形状
        screen_shape: (height, width, channels) 屏幕形状
        min_scale: 最小缩放比例
        max_scale: 最大缩放比例

    Returns:
        (min_scale, max_scale) 或 None 如果无效
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


def scan_best_scale_with_matcher(
    matcher: TemplateMatcher,
    img: Image.Image,
    template_name: str,
    min_scale: float = 0.1,
    max_scale: float = DEFAULT_MAX_SCALE,
    step: float = DEFAULT_STEP,
) -> Tuple[float, float]:
    """
    扫描所有缩放比例，返回最佳匹配的 (scale, confidence)

    Args:
        matcher: TemplateMatcher 实例
        img: 截图图像
        template_name: 模板名称
        min_scale: 最小缩放比例
        max_scale: 最大缩放比例
        step: 扫描步进

    Returns:
        (best_scale, best_confidence) 元组
    """
    import numpy as np

    best_scale = 1.0
    best_confidence = 0.0

    # 获取模板
    template = matcher.templates.get(template_name)
    if template is None:
        return best_scale, best_confidence

    orig_h, orig_w = template.shape[:2]

    # 获取截图尺寸
    screen = matcher._pil_to_cv2(img)

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
        match = matcher.find_with_scale(img, template_name, current_scale)
        confidence = match.confidence if match else 0.0
        if confidence > best_confidence:
            best_confidence = confidence
            best_scale = current_scale
        scale += step

    return best_scale, best_confidence


# 向后兼容的别名（用于 pack_tester.py）
scan_best_scale = scan_best_scale_with_matcher
