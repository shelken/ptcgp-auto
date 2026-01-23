# -*- coding: utf-8 -*-
"""
图片资源管理器

负责按需下载、处理和管理卡牌图片资源。
"""

import logging
import concurrent.futures
from pathlib import Path
from typing import List, Optional
from io import BytesIO

import requests
from PIL import Image
from sqlmodel import Session

from ptcgp_auto_v2.db.models import Card
from ptcgp_auto_v2.db.repositories import CardRepository
from ptcgp_auto_v2.db.engine import get_engine

logger = logging.getLogger(__name__)

# 图片处理配置
# 目标宽度（基于 1080p 分辨率下的卡牌大致宽度）
TARGET_WIDTH = 250
# 裁剪区域 (left, top, right, bottom) 比例
# 保留卡牌上半部分的插画，去除顶部边框和下半部分文字
CROP_BOX_RATIO = (0.05, 0.10, 0.95, 0.55)

IMAGE_BASE_URL = "https://raw.githubusercontent.com/flibustier/pokemon-tcg-exchange/main/public/images/cards"


class ImageResourceManager:
    """图片资源管理器"""

    def __init__(self, base_dir: str = "templates"):
        # 默认 base_dir 是相对于运行目录（项目根目录）的
        self.base_dir = Path(base_dir)
        self.cards_dir = self.base_dir / "cards"
        self.repo = CardRepository()
        self.session = requests.Session()
        # 设置请求头，模仿浏览器
        self.session.headers.update(
            {
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            }
        )

    def ensure_series_ready(self, series_code: str, rarity: Optional[str] = None, max_workers: int = 5):
        """
        确保指定系列的所有卡牌图片已准备就绪
        """
        logger.info(f"正在检查系列 {series_code} 的资源(rarity={rarity})...")
        cards = self.repo.get_cards_by_set(series_code)

        if not cards:
            logger.warning(f"系列 {series_code} 没有卡牌数据")
            return

        if rarity:
            original_count = len(cards)
            cards = [c for c in cards if c.rarity == rarity]
            logger.info(f"按稀有度 {rarity} 过滤: {original_count} -> {len(cards)}")

        self._process_cards_parallel(cards, max_workers)

    def ensure_pack_ready(self, pack_name: str, series_code: str, rarity: Optional[str] = None, max_workers: int = 5):
        """
        确保指定子包（如 "Mewtwo"）的所有卡牌图片已准备就绪
        """
        logger.info(f"正在检查卡包 {series_code}/{pack_name} 的资源(rarity={rarity})...")
        cards = self.repo.get_cards_by_pack(pack_name, series_code)

        if not cards:
            logger.warning(f"卡包 {series_code}/{pack_name} 没有卡牌数据")
            return

        if rarity:
            original_count = len(cards)
            cards = [c for c in cards if c.rarity == rarity]
            logger.info(f"按稀有度 {rarity} 过滤: {original_count} -> {len(cards)}")

        self._process_cards_parallel(cards, max_workers)

    def ensure_card_ready(self, card_id: int) -> bool:
        """确保单张卡牌资源就绪"""
        with Session(get_engine()) as session:
            card = session.get(Card, card_id)
            if not card:
                logger.error(f"Card {card_id} not found")
                return False
            return self._process_single_card(card)

    def process_cards(self, cards: List[Card], max_workers: int = 5):
        """
        并发处理指定的卡牌列表
        公开方法，用于外部传入已过滤的卡牌列表
        """
        self._process_cards_parallel(cards, max_workers)

    def _process_cards_parallel(self, cards: List[Card], max_workers: int):
        """并发处理卡牌列表"""
        pending_cards = []
        for card in cards:
            # 简单检查是否已存在（不仅检查 DB 字段，还要检查文件是否真的存在）
            if self._is_resource_valid(card):
                continue
            pending_cards.append(card)

        if not pending_cards:
            logger.info("所有资源已就绪")
            return

        logger.info(f"需要下载/处理 {len(pending_cards)} 张卡牌...")

        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
            # 提交任务
            future_to_card = {
                executor.submit(self._process_single_card, card): card
                for card in pending_cards
            }

            completed = 0
            for future in concurrent.futures.as_completed(future_to_card):
                card = future_to_card[future]
                try:
                    success = future.result()
                    if success:
                        completed += 1
                except Exception as e:
                    logger.error(f"处理卡牌 {card.name} 失败: {e}")

                if completed % 10 == 0:
                    # 使用 print 刷新进度，logger 可能会刷屏
                    print(f"进度: {completed}/{len(pending_cards)}", end="\r")
        print()  # 换行

    def _is_resource_valid(self, card: Card) -> bool:
        """检查卡牌资源是否有效（DB 有路径且文件存在）"""
        if not card.local_image_path:
            return False
        # 假设 local_image_path 是相对于项目根目录的路径 (templates/cards/...)
        return Path(card.local_image_path).exists()

    @staticmethod
    def normalize_name_str(name: str) -> str:
        """统一的文件名标准化逻辑：过滤特殊字符 + 空格转下划线"""
        # 保留字母数字、横杠、下划线、空格
        safe_name = "".join([c for c in name if c.isalnum() or c in " -_"])
        # 将空格替换为下划线
        return safe_name.replace(" ", "_")

    @staticmethod
    def get_card_filename(card: Card) -> str:
        """生成标准化的卡牌文件名 (空格替换为下划线)"""
        safe_name = ImageResourceManager.normalize_name_str(card.name)
        return f"{card.number:03d}_{safe_name}.png"

    def _process_single_card(self, card: Card) -> bool:
        """处理单张卡牌：下载 -> 裁剪 -> 保存 -> 更新DB"""
        if not card.image_url:
            return False

        try:
            # 获取该卡所属的所有 Packs
            pack_names = []

            # 使用新 Session 读取必要信息
            with Session(get_engine()) as session:
                db_card = session.get(Card, card.id)
                if not db_card:
                    return False
                pack_names = [p.pack_name for p in db_card.packs]

            if not pack_names:
                pack_names = ["_Misc"]

            # 构造完整 URL
            image_url = card.image_url
            if not image_url.startswith("http"):
                image_url = f"{IMAGE_BASE_URL}/{image_url}"

            # 下载图片
            img_data = self._download_image(image_url)
            if not img_data:
                return False

            img = Image.open(BytesIO(img_data))

            # 处理图片
            processed_img = self._crop_and_resize(img)

            # 保存到所有目标目录
            filename = self.get_card_filename(card)

            saved_paths = []

            for pack_name in pack_names:
                safe_pack = pack_name.replace(" ", "_")
                # 目录：templates/cards/{set_code}/{safe_pack}/
                save_dir = self.cards_dir / card.set_code / safe_pack
                save_dir.mkdir(parents=True, exist_ok=True)

                file_path = save_dir / filename
                processed_img.save(file_path, "PNG", optimize=True)

                rel_path = str(file_path)
                saved_paths.append(rel_path)

            # 更新数据库
            if saved_paths:
                with Session(get_engine()) as session:
                    db_card = session.get(Card, card.id)
                    if db_card:
                        db_card.local_image_path = saved_paths[0]
                        session.add(db_card)
                        session.commit()

            return True

        except Exception as e:
            logger.error(f"Error processing card {card.id} ({card.name}): {e}")
            return False

    def _download_image(self, url: str) -> Optional[bytes]:
        try:
            resp = self.session.get(url, timeout=15)
            if resp.status_code == 200:
                return resp.content
            return None
        except Exception as e:
            logger.warning(f"Download failed {url}: {e}")
            return None

    def _crop_and_resize(self, img: Image.Image) -> Image.Image:
        """
        裁剪并缩放图片
        """
        w, h = img.size

        # 1. 裁剪
        left = int(w * CROP_BOX_RATIO[0])
        top = int(h * CROP_BOX_RATIO[1])
        right = int(w * CROP_BOX_RATIO[2])
        bottom = int(h * CROP_BOX_RATIO[3])

        cropped = img.crop((left, top, right, bottom))

        # 2. 缩放 (保持比例)
        ratio = TARGET_WIDTH / cropped.width
        new_height = int(cropped.height * ratio)

        resized = cropped.resize((TARGET_WIDTH, new_height), Image.Resampling.LANCZOS)

        return resized
