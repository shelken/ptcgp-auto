# -*- coding: utf-8 -*-
"""
图片资源管理器

负责按需下载、处理和管理卡牌图片资源。
下载源使用 shelken/ptcgp-assets 仓库。
"""

import logging
import concurrent.futures
from pathlib import Path
from typing import List, Optional, Dict
from io import BytesIO

import requests
from PIL import Image
from sqlmodel import Session

from ptcgp_auto_v2.config.assets import build_card_image_bases
from ptcgp_auto_v2.config.lang import DEFAULT_LOCALE, locale_to_web_lang
from ptcgp_auto_v2.db.models import Card
from ptcgp_auto_v2.db.repositories import CardRepository
from ptcgp_auto_v2.db.engine import get_engine

logger = logging.getLogger(__name__)

# 使用 jsDelivr CDN 加速下载（跟随 DEFAULT_LOCALE 变化）
ASSETS_BASE_URL = build_card_image_bases(locale_to_web_lang(DEFAULT_LOCALE))[
    "cdn_base_url"
]


class ImageResourceManager:
    """图片资源管理器"""

    def __init__(self, base_dir: str = "templates/cards"):
        # 默认 base_dir 是相对于运行目录（项目根目录）的
        self.cards_dir = Path(base_dir)
        self.cards_dir.mkdir(parents=True, exist_ok=True)
        self.repo = CardRepository()
        self.session = requests.Session()
        # 设置请求头，模仿浏览器
        self.session.headers.update(
            {
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            }
        )

    def close(self):
        """关闭会话"""
        self.session.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    def ensure_series_ready(self, set_code: str, max_workers: int = 5) -> bool:
        """
        确保指定系列的所有卡牌图片已准备就绪

        Returns:
            True表示所有卡牌图片已就绪
        """
        logger.info(f"正在检查系列 {set_code} 的图片资源...")
        cards = self.repo.get_cards_by_set(set_code)

        if not cards:
            logger.warning(f"系列 {set_code} 没有卡牌数据")
            return False

        # 筛选出缺少本地图片的卡牌
        pending_cards = [c for c in cards if not self._is_resource_valid(c)]

        if not pending_cards:
            logger.info(f"系列 {set_code} 所有卡牌图片已就绪")
            return True

        logger.info(f"需要下载 {len(pending_cards)}/{len(cards)} 张卡牌图片...")
        self._process_cards_parallel(pending_cards, max_workers)

        return True

    def download_card(self, set_code: str, card_number: int) -> Optional[Path]:
        """
        下载单张卡牌图片，支持格式回退（png -> webp）

        Args:
            set_code: 系列代码（如 A1）
            card_number: 卡牌编号

        Returns:
            下载成功返回图片路径，失败返回None
        """
        # 确保目录存在
        save_dir = self.cards_dir / set_code
        save_dir.mkdir(parents=True, exist_ok=True)

        # 按优先级尝试不同格式：png优先，webp备用
        formats = [
            ("png", f"{card_number}.png"),
            ("webp", f"{card_number}.webp"),
        ]

        for ext, filename in formats:
            url = f"{ASSETS_BASE_URL}/{set_code}/{filename}"
            save_path = save_dir / filename

            # 如果已存在，直接返回
            if save_path.exists():
                return save_path

            try:
                resp = self.session.get(url, timeout=30)
                if resp.status_code == 200:
                    save_path.write_bytes(resp.content)
                    logger.debug(f"下载成功: {set_code}/{filename}")
                    return save_path
                elif resp.status_code == 404:
                    logger.debug(f"图片不存在(404): {url}")
                    continue  # 尝试下一个格式
                else:
                    logger.warning(f"下载失败({resp.status_code}): {url}")
            except Exception as e:
                logger.warning(f"下载异常: {url} - {e}")

        logger.warning(f"所有格式尝试失败: {set_code}/{card_number}")
        return None

    def download_cards_batch(
        self, set_code: str, card_numbers: List[int], max_workers: int = 5
    ) -> Dict[int, Path]:
        """
        批量下载卡牌图片

        Args:
            set_code: 系列代码
            card_numbers: 卡牌编号列表
            max_workers: 并发下载数

        Returns:
            {card_number: path} 下载成功的卡牌字典
        """
        results = {}

        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_card = {
                executor.submit(self.download_card, set_code, num): num
                for num in card_numbers
            }

            for future in concurrent.futures.as_completed(future_to_card):
                card_num = future_to_card[future]
                try:
                    path = future.result()
                    if path:
                        results[card_num] = path
                except Exception as e:
                    logger.error(f"下载卡牌 {set_code}/{card_num:03d} 出错: {e}")

        return results

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
        if not cards:
            return

        logger.info(f"开始下载/处理 {len(cards)} 张卡牌...")

        completed = 0
        failed = 0

        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
            # 提交任务 - 按系列分组下载
            future_to_card = {}
            for card in cards:
                future = executor.submit(self._process_single_card, card)
                future_to_card[future] = card

            for future in concurrent.futures.as_completed(future_to_card):
                card = future_to_card[future]
                try:
                    success = future.result()
                    if success:
                        completed += 1
                    else:
                        failed += 1
                except Exception as e:
                    logger.error(f"处理卡牌 {card.name} 失败: {e}")
                    failed += 1

                # 每10张打印进度
                total = completed + failed
                if total % 10 == 0:
                    logger.debug(f"进度: {completed}/{len(cards)} 成功, {failed} 失败")

        logger.info(f"处理完成: {completed} 成功, {failed} 失败")

    def _is_resource_valid(self, card: Card) -> bool:
        """检查卡牌资源是否有效（DB有路径且文件存在，支持png/webp）"""
        if not card.local_image_path:
            # 检查默认路径是否存在（支持png和webp）
            png_path = self.cards_dir / card.set_code / f"{card.number}.png"
            webp_path = self.cards_dir / card.set_code / f"{card.number}.webp"
            return png_path.exists() or webp_path.exists()

        # 假设 local_image_path 是相对于项目根目录的路径
        return Path(card.local_image_path).exists()

    def _process_single_card(self, card: Card) -> bool:
        """处理单张卡牌：下载 -> 保存 -> 更新DB"""
        if not card.number or not card.set_code:
            return False

        try:
            # 下载图片
            saved_path = self.download_card(card.set_code, card.number)

            if not saved_path:
                return False

            # 更新数据库（记录本地路径）
            with Session(get_engine()) as session:
                db_card = session.get(Card, card.id)
                if db_card:
                    db_card.local_image_path = str(saved_path)
                    session.add(db_card)
                    session.commit()

            return True

        except Exception as e:
            logger.error(f"Error processing card {card.id} ({card.name}): {e}")
            return False
