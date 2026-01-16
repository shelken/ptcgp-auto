"""
终端图片预览工具

支持 Kitty 图形协议，在终端中直接显示图片。
"""

import os
import subprocess
import sys
from pathlib import Path
from typing import Optional, Union
from PIL import Image


def _is_kitty() -> bool:
    """检测是否在 Kitty 终端中运行"""
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
    max_width: int = 40,
    max_height: int = 20,
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
        print("(终端不支持图片预览，跳过)")
        return False

    if not _has_icat():
        print("(未找到 kitten icat 命令，跳过预览)")
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
        )
        # 换行，避免后续输出覆盖图片
        print()
        return True
    except subprocess.CalledProcessError as e:
        print(f"(图片预览失败: {e})")
        return False
    except subprocess.TimeoutExpired:
        print("(图片预览超时)")
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
        subprocess.run(
            ["kitten", "icat", "--align", "left", image_path],
            check=True,
            timeout=10,
        )
        return True
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
