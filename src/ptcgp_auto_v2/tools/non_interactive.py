# -*- coding: utf-8 -*-
"""
调试工具 - 核心逻辑支持

提供模板加载等辅助功能
"""

import os
from pathlib import Path
from typing import Optional

import cv2

from ptcgp_auto import config


def _load_template_from_path(recognizer, template_path: str) -> Optional[str]:
    """
    从绝对路径或 ~ 路径加载模板，返回模板名称
    """
    # 展开 ~ 路径
    path = Path(os.path.expanduser(template_path))

    if not path.exists():
        print(f"ERROR: 模板文件不存在: {path}")
        return None

    if not path.suffix.lower() == ".png":
        print(f"WARNING: 模板文件不是 PNG 格式: {path}")
        return None

    # 使用文件名（不含扩展名）作为模板名
    template_name = path.stem

    # 加载模板图片
    img = cv2.imread(str(path))
    if img is None:
        print(f"ERROR: 无法读取模板文件: {path}")
        return None

    # 添加到识别器的模板字典中
    recognizer.templates[template_name] = img
    print(f"LOADED: {template_name} <- {path} ({img.shape[1]}x{img.shape[0]})")

    return template_name


def _find_and_load_system_template(recognizer, name: str) -> Optional[str]:
    """
    在 templates 目录下查找指定名称的模板并加载（带缩放）
    避免触发 Recognizer 的全量加载
    """
    # 规范化名称（去掉 .png）
    clean_name = name[:-4] if name.lower().endswith(".png") else name

    if clean_name in recognizer.templates:
        return clean_name

    root_dir = Path("templates")
    target_path = None

    # 1. 尝试直接拼接路径
    p = root_dir / f"{clean_name}.png"
    if p.exists():
        target_path = p
    else:
        # 2. 尝试递归搜索文件名
        candidates = list(root_dir.rglob(f"{clean_name}.png"))
        if candidates:
            target_path = candidates[0]

    if not target_path:
        return None

    # 加载并缩放
    img = cv2.imread(str(target_path))
    if img is None:
        print(f"ERROR: 无法读取模板: {target_path}")
        return None

    # 计算缩放
    scale = config.SCREEN_WIDTH / config.TEMPLATE_BASE_WIDTH
    if abs(scale - 1.0) > 0.01:
        new_w = int(img.shape[1] * scale)
        new_h = int(img.shape[0] * scale)
        img = cv2.resize(img, (new_w, new_h), interpolation=cv2.INTER_AREA)

    # 注册到 recognizer
    recognizer.templates[clean_name] = img
    print(f"LOADED: {clean_name} <- {target_path} ({img.shape[1]}x{img.shape[0]})")
    return clean_name
