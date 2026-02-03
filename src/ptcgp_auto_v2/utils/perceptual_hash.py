# -*- coding: utf-8 -*-
"""
感知哈希工具模块

提供卡牌图片的感知哈希计算和匹配功能。
基于 DCT（离散余弦变换）的感知哈希算法实现。
使用 scipy 进行加速（比纯Python实现快100-1000倍）。
"""

import base64
from dataclasses import dataclass
from typing import List

import cv2
import numpy as np
from PIL import Image
from scipy.fftpack import dct

# 哈希计算常量
HASH_SIZE = 96  # 预处理后的图片尺寸
FREQ_SIZE = 8  # DCT频率尺寸


@dataclass
class ColorPixels:
    """颜色像素数据"""

    r: List[int]
    g: List[int]
    b: List[int]


def pil_to_color_pixels(pil_image: Image.Image) -> ColorPixels:
    """从 PIL Image 转换为 ColorPixels"""
    # 去除 Alpha 通道（如果存在）
    if pil_image.mode == "RGBA":
        pil_image = pil_image.convert("RGB")
    elif pil_image.mode != "RGB":
        pil_image = pil_image.convert("RGB")

    # resize 使用 cubic
    pil_image = pil_image.resize((HASH_SIZE, HASH_SIZE), Image.Resampling.BICUBIC)

    # 转换为 numpy array
    rgb = np.array(pil_image)

    # 展平为列表
    color_pixels = ColorPixels(
        r=[0] * (HASH_SIZE * HASH_SIZE),
        g=[0] * (HASH_SIZE * HASH_SIZE),
        b=[0] * (HASH_SIZE * HASH_SIZE),
    )

    flat = rgb.reshape(-1, 3)
    for idx, (r, g, b) in enumerate(flat):
        color_pixels.r[idx] = int(r)
        color_pixels.g[idx] = int(g)
        color_pixels.b[idx] = int(b)

    return color_pixels


def bgr_to_color_pixels(bgr_image: np.ndarray) -> ColorPixels:
    """从 BGR 图片转换为 ColorPixels"""
    if bgr_image.ndim == 2:
        bgr_image = cv2.cvtColor(bgr_image, cv2.COLOR_GRAY2BGR)
    elif bgr_image.shape[2] == 4:
        bgr_image = cv2.cvtColor(bgr_image, cv2.COLOR_BGRA2BGR)

    resized = cv2.resize(
        bgr_image,
        (HASH_SIZE, HASH_SIZE),
        interpolation=cv2.INTER_CUBIC,
    )
    rgb = cv2.cvtColor(resized, cv2.COLOR_BGR2RGB)

    color_pixels = ColorPixels(
        r=[0] * (HASH_SIZE * HASH_SIZE),
        g=[0] * (HASH_SIZE * HASH_SIZE),
        b=[0] * (HASH_SIZE * HASH_SIZE),
    )

    flat = rgb.reshape(-1, 3)
    for idx, (r, g, b) in enumerate(flat):
        color_pixels.r[idx] = int(r)
        color_pixels.g[idx] = int(g)
        color_pixels.b[idx] = int(b)

    return color_pixels


def _compute_dct(pixels: List[int]) -> List[float]:
    """计算 DCT - 使用 scipy 加速"""
    n = int(np.sqrt(len(pixels)))
    if n * n != len(pixels):
        raise ValueError("像素长度不是平方数")

    # 转换为 numpy array 并 reshape
    img = np.array(pixels, dtype=np.float32).reshape(n, n)

    # 使用 scipy DCT (Type II) - 快 100-1000 倍
    dct_rows = dct(img, type=2, norm="ortho", axis=0)
    dct_2d = dct(dct_rows, type=2, norm="ortho", axis=1)

    # 只取前 FREQ_SIZE x FREQ_SIZE
    result = dct_2d[:FREQ_SIZE, :FREQ_SIZE].flatten().tolist()
    return result


def calculate_perceptual_hash(color_pixels: ColorPixels) -> np.ndarray:
    """计算感知哈希，返回 uint32 数组"""
    dct_r = _compute_dct(color_pixels.r)
    dct_g = _compute_dct(color_pixels.g)
    dct_b = _compute_dct(color_pixels.b)

    total_bits = 3 * (len(dct_r) - 1)
    buffer_len = int(np.ceil(total_bits / 32))
    arr = np.zeros(buffer_len, dtype=np.uint32)

    j = 0
    for dct in (dct_r, dct_g, dct_b):
        avg = float(np.mean(dct[1:]))
        for i in range(1, len(dct)):
            if dct[i] > avg + 1e-15:
                idx = j // 32
                bit = j % 32
                arr[idx] |= np.uint32(1 << bit)
            j += 1

    return arr


def calculate_similarity(hash1: np.ndarray, hash2: np.ndarray) -> float:
    """计算相似度（0~1），使用汉明距离"""
    if hash1.shape != hash2.shape:
        raise ValueError(f"哈希形状不匹配: {hash1.shape} vs {hash2.shape}")

    # XOR 后用 Python 3.10+ 的 int.bit_count()
    diff = hash1 ^ hash2
    distance = sum(x.bit_count() for x in diff)

    return 1.0 - distance / (3 * (FREQ_SIZE * FREQ_SIZE - 1))


def encode_hash_to_base64(hash_arr: np.ndarray) -> str:
    """将哈希数组编码为Base64字符串"""
    return base64.b64encode(hash_arr.tobytes()).decode("utf-8")


def decode_hash_from_base64(encoded: str) -> np.ndarray:
    """从Base64字符串解码哈希数组"""
    decoded_bytes = base64.b64decode(encoded)
    # 189位 = 6个uint32 (192位)
    return np.frombuffer(decoded_bytes, dtype=np.uint32)
