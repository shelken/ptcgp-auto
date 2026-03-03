# -*- coding: utf-8 -*-
"""
卡包图片资源管理器

负责从公共资源自动下载、处理和管理卡包封面图片。
来源: https://github.com/flibustier/pokemon-tcg-exchange
"""

import logging
import time
from io import BytesIO
from pathlib import Path
from typing import Optional
from urllib.parse import quote

import requests
from PIL import Image

from ptcgp_auto_v2.utils.card_naming import normalize_name_str

logger = logging.getLogger(__name__)

# 配置参数（基于测试可调整）
# 公共图片基础 URL（优先 jsDelivr，失败回退 GitHub Raw）
PACK_IMAGE_BASE_URLS = [
    "https://cdn.jsdelivr.net/gh/flibustier/pokemon-tcg-exchange@main/public/images/packs",
    "https://raw.githubusercontent.com/flibustier/pokemon-tcg-exchange/main/public/images/packs",
]

# 下载重试与超时
PACK_IMAGE_DOWNLOAD_RETRIES = 3
PACK_IMAGE_DOWNLOAD_TIMEOUT = 15

# 裁剪区域比例 (left, top, right, bottom)
# 通过交互式 ROI 测试确定的最佳参数
# 来源: 160x256 WebP 图片需裁剪为 103x95 (比例 1.085)
# Left: 18%, Top: 23%, Right: 82%, Bottom: 60%
# 原始图片尺寸: 160x256 -> 裁剪后: 103x95 -> 缩放后: 513x473
# 匹配缩放比例: 0.81, 置信度: 0.9057
PACK_CROP_RATIO = (0.18, 0.23, 0.82, 0.44)

# 目标宽度（与旧手动模板一致 513px）
TARGET_WIDTH = 513

# 标准卡包图片尺寸（用于计算比例）
# 来源: GitHub 上的标准卡包图片尺寸为 160x256
STANDARD_PACK_WIDTH = 160
STANDARD_PACK_HEIGHT = 256


class PackImageManager:
    """
    卡包图片资源管理器

    负责从 GitHub 公共资源下载卡包封面，进行裁剪和缩放处理后保存。
    """

    def __init__(self, base_dir: str = "templates/packs_auto"):
        """
        初始化管理器

        Args:
            base_dir: 卡包图片保存的基础目录
        """
        self.base_dir = Path(base_dir)
        self.base_dir.mkdir(parents=True, exist_ok=True)

        # 创建会话，设置 User-Agent
        self.session = requests.Session()
        self.session.headers.update(
            {
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
            }
        )

    def close(self):
        """关闭会话"""
        self.session.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    def ensure_pack_ready(self, booster_name: str) -> bool:
        """
        确保指定卡包图片已准备就绪

        Args:
            booster_name: 子包名称，如 "Charizard", "Mewtwo"

        Returns:
            True 表示资源就绪，False 表示失败
        """
        pack_path = self.get_pack_path(booster_name)
        if self.is_pack_ready(booster_name):
            return True

        logger.info(f"准备卡包图片资源: {booster_name}")

        # 下载图片
        image_data = self.download_pack_image(booster_name)
        if not image_data:
            logger.error(f"下载卡包图片失败: {booster_name}")
            return False

        # 处理并保存
        return self.process_and_save(booster_name, image_data)

    def is_pack_ready(self, booster_name: str) -> bool:
        """
        检查卡包图片是否已存在且有效

        Args:
            booster_name: 子包名称

        Returns:
            True 表示资源已就绪
        """
        pack_path = self.get_pack_path(booster_name)
        if not pack_path.exists():
            return False

        # 检查文件是否有效（至少 1KB）
        if pack_path.stat().st_size < 1024:
            return False

        return True

    def download_pack_image(self, booster_name: str) -> Optional[bytes]:
        """
        从 GitHub 下载卡包图片

        Args:
            booster_name: 子包名称

        Returns:
            图片二进制数据，失败返回 None
        """
        # 构造 URL（保留空格转义）
        encoded_name = quote(booster_name, safe="")

        for base_url in PACK_IMAGE_BASE_URLS:
            url = f"{base_url}/{encoded_name}.webp"
            for attempt in range(1, PACK_IMAGE_DOWNLOAD_RETRIES + 1):
                try:
                    logger.debug(
                        f"下载卡包图片: {url} (尝试 {attempt}/{PACK_IMAGE_DOWNLOAD_RETRIES})"
                    )
                    resp = self.session.get(url, timeout=PACK_IMAGE_DOWNLOAD_TIMEOUT)
                    if resp.status_code == 200 and resp.content:
                        return resp.content
                    logger.warning(
                        f"下载失败: {url} (HTTP {resp.status_code}, 尝试 {attempt}/{PACK_IMAGE_DOWNLOAD_RETRIES})"
                    )
                except Exception as e:
                    logger.warning(
                        f"下载异常: {url} - {e} (尝试 {attempt}/{PACK_IMAGE_DOWNLOAD_RETRIES})"
                    )
                time.sleep(0.5 * attempt)

        return None

    def process_and_save(self, booster_name: str, image_data: bytes) -> bool:
        """
        处理并保存卡包图片

        处理流程:
        1. 打开 WebP 图片
        2. 裁剪去除边框（保留原始尺寸，不缩放）
        3. 保存为 PNG

        注: 模板匹配器会在加载时根据屏幕比例自动缩放，
            因此不需要在这里缩放，可以减小文件大小

        Args:
            booster_name: 子包名称
            image_data: 图片二进制数据

        Returns:
            True 表示成功
        """
        try:
            # 打开图片
            img = Image.open(BytesIO(image_data))

            # 1. 裁剪（不缩放，保持裁剪后尺寸）
            processed_img = self._crop_image(img)

            # 2. 保存
            save_path = self.get_pack_path(booster_name)
            processed_img.save(save_path, "PNG", optimize=True)

            logger.info(
                f"卡包图片已保存: {save_path} ({processed_img.width}x{processed_img.height})"
            )
            return True

        except Exception as e:
            logger.error(f"处理卡包图片失败: {booster_name} - {e}")
            return False

    def _crop_image(self, img: Image.Image) -> Image.Image:
        """
        裁剪图片，去除边框

        通用处理逻辑：
        1. 如果图片比例不符合标准（160:256），先从中心裁剪出标准比例的区域
        2. 然后应用 PACK_CROP_RATIO 进行最终裁剪

        Args:
            img: 原始图片

        Returns:
            裁剪后的图片（RGB 模式，不含透明通道）
        """
        w, h = img.size
        current_ratio = w / h
        standard_ratio = STANDARD_PACK_WIDTH / STANDARD_PACK_HEIGHT

        # 如果比例不匹配（有额外边框），先从中心裁剪出标准比例的区域
        if abs(current_ratio - standard_ratio) > 0.01:  # 允许 1% 误差
            if current_ratio > standard_ratio:
                # 图片太宽，从左右裁剪
                new_width = int(h * standard_ratio)
                left = (w - new_width) // 2
                right = left + new_width
                img = img.crop((left, 0, right, h))
            else:
                # 图片太高，从上下裁剪（理论上不应该出现）
                new_height = int(w / standard_ratio)
                top = (h - new_height) // 2
                bottom = top + new_height
                img = img.crop((0, top, w, bottom))
            w, h = img.size

        left = int(w * PACK_CROP_RATIO[0])
        top = int(h * PACK_CROP_RATIO[1])
        right = int(w * PACK_CROP_RATIO[2])
        bottom = int(h * PACK_CROP_RATIO[3])

        cropped = img.crop((left, top, right, bottom))

        # 转换为 RGB 模式（去除透明通道，与旧模板一致）
        if cropped.mode == "RGBA":
            # 创建白色背景
            background = Image.new("RGB", cropped.size, (255, 255, 255))
            background.paste(
                cropped, mask=cropped.split()[3]
            )  # 使用 alpha 通道作为 mask
            return background
        elif cropped.mode != "RGB":
            return cropped.convert("RGB")

        return cropped

    def _resize_image(self, img: Image.Image) -> Image.Image:
        """
        缩放图片到目标宽度

        Args:
            img: 原始图片

        Returns:
            缩放后的图片
        """
        ratio = TARGET_WIDTH / img.width
        new_height = int(img.height * ratio)

        return img.resize((TARGET_WIDTH, new_height), Image.Resampling.LANCZOS)

    def get_pack_path(self, booster_name: str) -> Path:
        """
        获取卡包图片保存路径

        Args:
            booster_name: 子包名称

        Returns:
            保存路径（PNG 格式）
        """
        # 使用规范化名称作为文件名（替换空格为下划线）
        safe_name = normalize_name_str(booster_name)
        return self.base_dir / f"{safe_name}.png"

    def get_template_name(self, booster_name: str) -> str:
        """
        获取模板名称（用于 TemplateMatcher）

        Args:
            booster_name: 子包名称

        Returns:
            模板名称，如 "packs_auto/Charizard"
        """
        safe_name = normalize_name_str(booster_name)
        return f"packs_auto/{safe_name}"

    def list_available_packs(self) -> list[str]:
        """
        列出所有已下载的卡包

        Returns:
            卡包名称列表
        """
        if not self.base_dir.exists():
            return []

        packs = []
        for file in self.base_dir.glob("*.png"):
            packs.append(file.stem)

        return sorted(packs)

    def delete_pack(self, booster_name: str) -> bool:
        """
        删除指定卡包图片

        Args:
            booster_name: 子包名称

        Returns:
            True 表示成功删除
        """
        pack_path = self.get_pack_path(booster_name)
        if pack_path.exists():
            pack_path.unlink()
            logger.info(f"已删除卡包图片: {pack_path}")
            return True
        return False

    def clear_all(self) -> int:
        """
        清除所有卡包图片

        Returns:
            删除的文件数量
        """
        count = 0
        if self.base_dir.exists():
            for file in self.base_dir.glob("*.png"):
                file.unlink()
                count += 1
            logger.info(f"已清除 {count} 个卡包图片")
        return count
