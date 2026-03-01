# -*- coding: utf-8 -*-
"""
模板加载工具

提供按需加载模板的功能，避免触发 Recognizer 的全量模板加载。
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import TYPE_CHECKING

import cv2

from ptcgp_auto import config

if TYPE_CHECKING:
    from typing import Optional
    from ptcgp_auto.recognizer import Recognizer


# =============================================================================
# 模板加载函数
# =============================================================================


def load_template_from_path(recognizer: Recognizer, template_path: str) -> Optional[str]:
    """
    从绝对路径或 ~ 路径加载模板

    支持绝对路径、相对路径和 ~ 展开的家目录路径。
    模板将被注册到 recognizer.templates 字典中，使用文件名（不含扩展名）作为键。

    Args:
        recognizer: Recognizer 实例
        template_path: 模板文件路径

    Returns:
        成功返回模板名称（stem），失败返回 None

    Example:
        >>> name = load_template_from_path(recognizer, "~/templates/icon_yes.png")
        >>> print(name)  # "icon_yes"
    """
    path = Path(os.path.expanduser(template_path))

    if not path.exists():
        print(f"ERROR: 模板文件不存在: {path}")
        return None

    if path.suffix.lower() != ".png":
        print(f"WARNING: 模板文件不是 PNG 格式: {path}")
        return None

    template_name = path.stem

    img = cv2.imread(str(path))
    if img is None:
        print(f"ERROR: 无法读取模板文件: {path}")
        return None

    recognizer.templates[template_name] = img
    print(f"LOADED: {template_name} <- {path} ({img.shape[1]}x{img.shape[0]})")

    return template_name


def load_system_template(recognizer: Recognizer, name: str) -> Optional[str]:
    """
    从系统 templates 目录查找并加载模板

    搜索顺序:
    1. 检查 recognizer.templates 中是否已存在
    2. 尝试 templates/{name}.png
    3. 递归搜索 templates/ 下所有子目录

    找到的模板会根据屏幕分辨率自动缩放（基于 1080p 基准）。

    Args:
        recognizer: Recognizer 实例
        name: 模板名称（可带或不带 .png 后缀）

    Returns:
        成功返回模板名称，失败返回 None

    Example:
        >>> name = load_system_template(recognizer, "icon_yes")
        >>> print(name)  # "icon_yes"
    """
    # 规范化名称（去掉 .png 后缀）
    clean_name = name[:-4] if name.lower().endswith(".png") else name

    # 已加载则直接返回
    if clean_name in recognizer.templates:
        return clean_name

    root_dir = Path("templates")
    target_path = _find_template_file(root_dir, clean_name)

    if target_path is None:
        return None

    img = cv2.imread(str(target_path))
    if img is None:
        print(f"ERROR: 无法读取模板: {target_path}")
        return None

    # 根据基准分辨率缩放模板
    img = _scale_template_to_screen(img)

    recognizer.templates[clean_name] = img
    print(f"LOADED: {clean_name} <- {target_path} ({img.shape[1]}x{img.shape[0]})")
    return clean_name


# =============================================================================
# 内部函数
# =============================================================================


def _find_template_file(root_dir: Path, name: str) -> Optional[Path]:
    """
    查找模板文件

    Args:
        root_dir: 模板根目录
        name: 模板名称（不含扩展名）

    Returns:
        文件路径或 None
    """
    # 1. 尝试直接路径
    direct_path = root_dir / f"{name}.png"
    if direct_path.exists():
        return direct_path

    # 2. 递归搜索
    candidates = list(root_dir.rglob(f"{name}.png"))
    return candidates[0] if candidates else None


def _scale_template_to_screen(img) -> cv2.ndarray:
    """
    根据屏幕分辨率缩放模板图像

    基准分辨率为 1080x1920，计算缩放比例并应用到模板。

    Args:
        img: OpenCV 图像数组

    Returns:
        缩放后的图像数组
    """
    scale = config.SCREEN_WIDTH / config.TEMPLATE_BASE_WIDTH

    if abs(scale - 1.0) <= 0.01:
        return img

    new_w = int(img.shape[1] * scale)
    new_h = int(img.shape[0] * scale)
    return cv2.resize(img, (new_w, new_h), interpolation=cv2.INTER_AREA)


# =============================================================================
# 向后兼容的别名（用于 pack_tester.py）
# =============================================================================

_load_template_from_path = load_template_from_path
_find_and_load_system_template = load_system_template
