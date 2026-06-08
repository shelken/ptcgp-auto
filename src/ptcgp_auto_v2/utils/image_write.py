# -*- coding: utf-8 -*-
"""图片文件写入工具。"""

from __future__ import annotations

from io import BytesIO
import os
from pathlib import Path
import threading
from typing import Any

from PIL import Image


def atomic_temp_path(path: Path) -> Path:
    """生成同目录临时文件路径，确保 replace 不跨文件系统。"""
    return path.with_name(f".{path.name}.{os.getpid()}.{threading.get_ident()}.tmp")


def write_bytes_atomic(path: Path, content: bytes) -> None:
    """原子写入文件，避免读者看到半写入内容。"""
    temp_path = atomic_temp_path(path)
    try:
        temp_path.write_bytes(content)
        temp_path.replace(path)
    except Exception:
        temp_path.unlink(missing_ok=True)
        raise


def save_pil_image_atomic(
    image: Image.Image,
    path: Path,
    image_format: str,
    **save_kwargs: Any,
) -> None:
    """先完整编码图片，再原子替换目标文件。"""
    buffer = BytesIO()
    image.save(buffer, image_format, **save_kwargs)
    write_bytes_atomic(path, buffer.getvalue())
