# -*- coding: utf-8 -*-
"""
终端图片预览工具
支持 Kitty 图形协议，在终端中直接显示图片。
(移植自 v1 src/ptcgp_auto/debug_tools/terminal_preview.py)
"""

import os
import subprocess
import sys
from pathlib import Path
from typing import Optional, Union
from PIL import Image


def _is_kitty() -> bool:
    """检测是否在 Kitty 终端中运行"""
    # 只要环境变量符合就尝试运行，通过捕获 stderr 来处理不支持的情况
    return os.environ.get("TERM", "").startswith("xterm-kitty") or \
           os.environ.get("KITTY_WINDOW_ID") is not None


def _has_icat() -> bool:
    """检测是否有 kitten icat 命令"""
    try:
        result = subprocess.run(
            ["kitten", "icat", "--help"],
            capture_output=True,
            timeout=5
        )
        return result.returncode == 0
    except Exception:
        return False


def preview_image(
    image: Union[Path, str, Image.Image],
    max_width: int = 80,
    max_height: int = 40,
) -> bool:
    """
    在终端中预览图片

    Args:
        image: 图片路径或 PIL Image 对象
        max_width: 最大宽度（字符列数）
        max_height: 最大高度（字符行数）

    Returns:
        是否成功显示
    """
    # 检测终端支持
    if not _is_kitty():
        return False

    if not _has_icat():
        return False

    # 处理图片来源
    temp_file = None
    if isinstance(image, Image.Image):
        # PIL Image，保存为临时文件
        import tempfile
        temp_file = tempfile.NamedTemporaryFile(suffix=".png", delete=False)
        image.save(temp_file.name)
        image_path = temp_file.name
    else:
        image_path = str(image)

    try:
        # 使用 kitten icat 显示图片
        # 关键点：设置 stderr=subprocess.PIPE 以捕获错误信息
        # 如果终端不支持协议（如 tmux/zellij），icat 会输出错误到 stderr 并返回非 0
        # 我们捕获这个错误并静默处理，避免污染控制台输出
        subprocess.run(
            [
                "kitten", "icat",
                "--align", "left",
                "--scale-up",
                f"--place={max_width}x{max_height}@0x0",
                image_path,
            ],
            check=True,
            timeout=10,
            stderr=subprocess.PIPE,  # 捕获 stderr，静默协议错误
        )
        # 换行，避免后续输出覆盖图片
        print()
        return True
    except subprocess.CalledProcessError:
        # 执行失败（通常是 Protocol not supported），静默返回
        return False
    except subprocess.TimeoutExpired:
        # 超时也不报错
        return False
    finally:
        # 清理临时文件
        if temp_file:
            try:
                os.unlink(temp_file.name)
            except Exception:
                pass


def preview_image_inline(
    image: Union[Path, str, Image.Image],
) -> bool:
    """
    在终端中内联预览图片（不使用 place 模式）

    更简单的预览方式，图片会按终端宽度自动缩放。

    Args:
        image: 图片路径或 PIL Image 对象

    Returns:
        是否成功显示
    """
    if not _is_kitty() or not _has_icat():
        return False

    temp_file = None
    if isinstance(image, Image.Image):
        import tempfile
        temp_file = tempfile.NamedTemporaryFile(suffix=".png", delete=False)
        image.save(temp_file.name)
        image_path = temp_file.name
    else:
        image_path = str(image)

    try:
        # 同上，捕获 stderr 以静默错误
        subprocess.run(
            ["kitten", "icat", "--align", "left", image_path],
            check=True,
            timeout=10,
            stderr=subprocess.PIPE,
        )
        return True
    except subprocess.CalledProcessError:
        # 静默失败
        return False
    except Exception:
        return False
    finally:
        if temp_file:
            try:
                os.unlink(temp_file.name)
            except Exception:
                pass


def get_terminal_support() -> str:
    """
    获取当前终端的图片支持情况

    Returns:
        支持情况描述
    """
    if _is_kitty():
        if _has_icat():
            return "kitty (kitten icat)"
        return "kitty (无 icat)"
    return "不支持"