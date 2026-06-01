# -*- coding: utf-8 -*-
"""
卡包图片资源管理器

负责从 ptcgp-assets 下载、处理和管理卡包封面图片。
"""

import logging
import time
from io import BytesIO
from pathlib import Path
from typing import Any, Optional

import requests
from PIL import Image

from ptcgp_auto_v2.config.assets import build_pack_image_url
from ptcgp_auto_v2.db.engine import session_scope
from ptcgp_auto_v2.db.repositories.card_repository import CardRepository, PackData
from ptcgp_auto_v2.services.metadata_sync.flibustier_sync_service import SETS_URL
from ptcgp_auto_v2.utils.card_naming import normalize_name_str

logger = logging.getLogger(__name__)

# 配置参数（基于测试可调整）
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

# 标准卡包图片尺寸（用于计算比例）
# 来源: GitHub 上的标准卡包图片尺寸为 160x256
STANDARD_PACK_WIDTH = 160
STANDARD_PACK_HEIGHT = 256


class PackImageManager:
    """
    卡包图片资源管理器

    之前这里把下载/处理失败直接抛异常，调用方会被整条链路打断。
    现在恢复为资源准备失败返回 False，让模板匹配调用方自己决定是否降级。
    该类覆盖卡包图片下载、裁剪保存与模板路径映射，依赖 requests 和 PIL。
    """

    def __init__(self, base_dir: str = "templates/packs_auto_assets"):
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
        self._remote_pack_image_cache: dict[str, tuple[str, str]] | None = None

    def close(self):
        """关闭会话"""
        self.session.close()

    def __enter__(self):
        return self

    def __exit__(self, _exc_type, _exc_val, _exc_tb):
        self.close()

    def ensure_pack_ready(self, booster_name: str) -> bool:
        """
        确保指定卡包图片已准备就绪

        Args:
            booster_name: 子包名称，如 "Charizard", "Mewtwo"

        Returns:
            True 表示资源就绪，False 表示失败
        """
        if self.is_pack_ready(booster_name):
            return True

        logger.info(f"准备卡包图片资源: {booster_name}")

        pack_data = self.get_pack_metadata(booster_name)
        image_url = pack_data.image_url if pack_data else None
        sku_id = pack_data.sku_id if pack_data else None
        if not image_url:
            remote_metadata = self.resolve_remote_pack_image(booster_name)
            if remote_metadata is None:
                logger.error("准备卡包图片失败，缺少 sku/image_url: booster=%s sku_id=%s", booster_name, sku_id)
                return False
            sku_id, image_url = remote_metadata

        image_data = self.download_pack_image(image_url, booster_name, sku_id)
        if image_data is None:
            logger.error("准备卡包图片失败，下载未成功: booster=%s sku_id=%s", booster_name, sku_id)
            return False

        return self.process_and_save(booster_name, image_data)

    def get_pack_metadata(self, booster_name: str) -> PackData | None:
        """从数据库读取卡包图片元数据。"""
        with session_scope() as session:
            return CardRepository(session).get_pack_by_name(booster_name)

    def resolve_remote_pack_image(self, booster_name: str) -> tuple[str, str] | None:
        """从 ptcgp-assets sets.json 解析本次下载需要的包图 URL，不写回数据库。"""
        if self._remote_pack_image_cache is None:
            self._remote_pack_image_cache = self._load_remote_pack_image_cache()
        return self._remote_pack_image_cache.get(booster_name)

    def _load_remote_pack_image_cache(self) -> dict[str, tuple[str, str]]:
        try:
            resp = self.session.get(SETS_URL, timeout=PACK_IMAGE_DOWNLOAD_TIMEOUT)
            if resp.status_code != 200:
                logger.warning("读取远端 sets.json 失败: HTTP %s", resp.status_code)
                return {}
            sets_data = resp.json()
        except Exception:
            logger.exception("读取远端 sets.json 异常")
            return {}

        cache: dict[str, tuple[str, str]] = {}
        for set_item in self._iter_set_items(sets_data):
            for raw_pack_entry in set_item.get("packs") or []:
                if not isinstance(raw_pack_entry, dict):
                    continue
                pack_name = str(raw_pack_entry.get("name") or "").strip()
                sku_id = str(raw_pack_entry.get("skuId") or "").strip()
                if not pack_name or not sku_id:
                    continue
                # 变更原因：未同步 DB 时只能用远端 skuId 生成本次下载 URL，禁止写库自修复。
                cache[pack_name] = (sku_id, build_pack_image_url(sku_id))
        return cache

    def _iter_set_items(self, sets_data: Any) -> list[dict[str, Any]]:
        if isinstance(sets_data, dict):
            raw_sets = sets_data.get("sets")
            if isinstance(raw_sets, list):
                return [item for item in raw_sets if isinstance(item, dict)]
            return [item for value in sets_data.values() if isinstance(value, list) for item in value if isinstance(item, dict)]
        if isinstance(sets_data, list):
            return [item for item in sets_data if isinstance(item, dict)]
        return []

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

    def download_pack_image(self, image_url: str, booster_name: str | None = None, sku_id: str | None = None) -> Optional[bytes]:
        """
        从数据库记录的 URL 下载卡包图片。

        Args:
            image_url: ptcgp-assets 包图 URL
            booster_name: 子包名称，用于日志
            sku_id: 游戏资源 SKU，用于日志

        Returns:
            图片二进制数据，失败返回 None
        """
        for attempt in range(1, PACK_IMAGE_DOWNLOAD_RETRIES + 1):
            try:
                logger.debug(
                    "下载卡包图片: %s (booster=%s sku_id=%s 尝试 %s/%s)",
                    image_url,
                    booster_name,
                    sku_id,
                    attempt,
                    PACK_IMAGE_DOWNLOAD_RETRIES,
                )
                resp = self.session.get(image_url, timeout=PACK_IMAGE_DOWNLOAD_TIMEOUT)
                if resp.status_code == 200 and resp.content:
                    return resp.content
                if resp.status_code == 404:
                    logger.warning("卡包图片不存在: %s booster=%s sku_id=%s", image_url, booster_name, sku_id)
                    break
                logger.warning(
                    "下载失败: %s (HTTP %s, booster=%s sku_id=%s, 尝试 %s/%s)",
                    image_url,
                    resp.status_code,
                    booster_name,
                    sku_id,
                    attempt,
                    PACK_IMAGE_DOWNLOAD_RETRIES,
                )
            except Exception:
                logger.exception(
                    "下载卡包图片异常: %s booster=%s sku_id=%s (尝试 %s/%s)",
                    image_url,
                    booster_name,
                    sku_id,
                    attempt,
                    PACK_IMAGE_DOWNLOAD_RETRIES,
                )
            time.sleep(0.5 * attempt)

        logger.error("下载卡包图片失败: booster=%s sku_id=%s", booster_name, sku_id)
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

        except Exception:
            logger.exception("处理卡包图片失败: %s", booster_name)
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
            模板名称，如 "packs_auto_assets/Charizard"
        """
        safe_name = normalize_name_str(booster_name)
        return f"{self.base_dir.name}/{safe_name}"

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
