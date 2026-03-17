# -*- coding: utf-8 -*-
"""
终端图片预览工具
支持 Kitty 图形协议，在终端中直接显示图片。
(移植自 v1 src/ptcgp_auto/debug_tools/terminal_preview.py)
"""

import os
import subprocess
from pathlib import Path
from typing import Union

from PIL import Image


def _is_kitty() -> bool:
    """检测是否在 Kitty 终端中运行"""
    # 只要环境变量符合就尝试运行，通过捕获 stderr 来处理不支持的情况
    return (
        os.environ.get("TERM", "").startswith("xterm-kitty")
        or os.environ.get("KITTY_WINDOW_ID") is not None
    )


def _has_icat() -> bool:
    """检测是否有 kitten icat 命令"""
    try:
        result = subprocess.run(
            ["kitten", "icat", "--help"], capture_output=True, timeout=5
        )
        return result.returncode == 0
    except Exception:
        return False


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
