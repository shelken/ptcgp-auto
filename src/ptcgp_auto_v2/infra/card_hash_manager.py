# -*- coding: utf-8 -*-
"""
卡牌Hash管理器

管理内存中的Hash索引，负责确保系列Hash就绪，提供匹配接口。
"""

import logging
import threading
from typing import Dict, List, Optional, Set, Tuple

import numpy as np
from PIL import Image

from ptcgp_auto_v2.config.constants import (
    HASH_SIMILARITY_TIE_THRESHOLD,
    TOPK_CANDIDATES,
)
from ptcgp_auto_v2.db.engine import session_scope
from ptcgp_auto_v2.db.repositories import CardRepository
from ptcgp_auto_v2.utils.image_manager import ImageResourceManager
from ptcgp_auto_v2.utils.perceptual_hash import (
    calculate_perceptual_hash,
    calculate_similarity,
    decode_hash_from_base64,
    encode_hash_to_base64,
    pil_to_color_pixels,
)

logger = logging.getLogger(__name__)


class CardHashManager:
    """卡牌Hash管理器"""

    def __init__(self, enable_download: bool = True):
        # 按系列索引（开包识别用）
        self._series_cache: Dict[str, Dict[int, np.ndarray]] = {}
        # 全局索引（跨系列检测用）
        self._global_cache: Dict[str, np.ndarray] = {}  # key: "A1/001"
        self._loaded_sets: Set[str] = set()
        self._all_loaded: bool = False
        # 内存缓存：记录下载失败的卡牌，避免重复尝试（按卡牌粒度）
        self._failed_downloads: Set[str] = set()  # 格式: "{set_code}/{number:03d}"
        self._downloader = ImageResourceManager() if enable_download else None
        self._enable_download = enable_download

    def ensure_series_ready(self, set_code: str, exclude_promo: bool = False) -> bool:
        """确保某系列所有卡牌都有Hash值（下载缺失卡牌并计算）

        Args:
            set_code: 系列代码
            exclude_promo: 是否排除 PROMO 系列（开包场景使用）
        """
        # 排除 PROMO 系列
        if exclude_promo and set_code.upper().startswith("PROMO"):
            logger.debug(f"[HashManager] 跳过 PROMO 系列: {set_code}")
            return True

        # 1. 查询缺失Hash的卡牌
        with session_scope() as session:
            all_missing = [
                (card.id, card.number)
                for card in CardRepository(session).get_cards_without_hash(set_code)
                if card.id is not None
            ]

        # 2. 过滤掉已下载失败的卡牌（内存缓存，避免重复尝试）
        missing_cards = [
            (card_id, number)
            for card_id, number in all_missing
            if f"{set_code}/{number:03d}" not in self._failed_downloads
        ]

        skipped_count = len(all_missing) - len(missing_cards)
        if skipped_count > 0:
            logger.debug(f"系列 {set_code} 跳过 {skipped_count} 张已知下载失败的卡牌")

        if missing_cards:
            if not self._enable_download:
                # 下载被禁用，仅记录警告
                logger.warning(
                    f"系列 {set_code} 有 {len(missing_cards)} 张卡牌缺少Hash，"
                    f"但下载功能已禁用，跳过处理"
                )
            else:
                logger.info(
                    f"系列 {set_code} 有 {len(missing_cards)} 张卡牌缺少Hash，开始处理..."
                )

                # 3. 下载缺失卡牌的图片
                card_numbers = [number for _, number in missing_cards]
                downloaded = self._downloader.download_cards_batch(  # type: ignore
                    set_code, card_numbers
                )

                # 4. 计算Hash并更新数据库
                success_count = 0
                for card_id, number in missing_cards:
                    if number in downloaded:
                        if self._compute_and_save_hash(card_id, downloaded[number]):
                            success_count += 1
                    else:
                        # 下载失败，记录到内存缓存，本次运行不再尝试
                        self._failed_downloads.add(f"{set_code}/{number:03d}")
                        logger.warning(
                            f"卡牌 {set_code}/{number:03d} 下载失败，已标记为失败（本次运行不再尝试）"
                        )

                logger.info(
                    f"系列 {set_code} Hash计算完成: {success_count}/{len(missing_cards)} 张成功"
                )

        # 5. 加载系列Hash到内存
        self._load_series_hash(set_code)

        return True

    def _compute_and_save_hash(self, card_id: int, image_path) -> bool:
        """计算图片Hash并保存到数据库"""
        try:
            # 读取图片
            pil_img = Image.open(image_path)

            # 计算Hash
            color_pixels = pil_to_color_pixels(pil_img)
            hash_arr = calculate_perceptual_hash(color_pixels)

            # 编码为Base64
            hash_str = encode_hash_to_base64(hash_arr)

            # 更新数据库
            with session_scope() as session:
                return CardRepository(session).update_card_hash(card_id, hash_str)
        except Exception as e:
            logger.exception("计算卡牌 Hash 失败: %s", card_id)
            raise RuntimeError(f"计算卡牌 Hash 失败: {card_id}") from e

    def _load_series_hash(self, set_code: str):
        """加载某系列Hash到内存（系列模式）"""
        if set_code in self._loaded_sets:
            return

        with session_scope() as session:
            hash_data = CardRepository(session).get_cards_with_hash_by_set(set_code)

        self._series_cache[set_code] = {
            number: decode_hash_from_base64(hash_str)
            for number, hash_str in hash_data.items()
        }
        self._loaded_sets.add(set_code)

        logger.debug(f"系列 {set_code} Hash索引加载完成，共 {len(hash_data)} 张卡牌")

    def load_all_hashes(self, exclude_promo: bool = False) -> bool:
        """加载所有系列Hash到内存（全局模式）

        Args:
            exclude_promo: 是否排除 PROMO 系列
        """
        if self._all_loaded and not exclude_promo:
            return True

        # 获取所有系列
        with session_scope() as session:
            all_set_codes = [item.code for item in CardRepository(session).get_all_sets()]

        for set_code in all_set_codes:
            # 排除 PROMO 系列
            if exclude_promo and set_code.upper().startswith("PROMO"):
                logger.debug(f"[HashManager] 加载全局Hash时跳过 PROMO 系列: {set_code}")
                continue
            # 确保系列就绪（下载缺失图片并计算Hash）
            self.ensure_series_ready(set_code, exclude_promo=exclude_promo)
            # 加载到全局缓存
            if set_code in self._series_cache:
                for number, hash_arr in self._series_cache[set_code].items():
                    self._global_cache[f"{set_code}/{number:03d}"] = hash_arr

        if not exclude_promo:
            self._all_loaded = True
        logger.debug(f"全局Hash索引加载完成，共 {len(self._global_cache)} 张卡牌")
        return True

    def find_best_match(
        self,
        target_hash: np.ndarray,
        set_code: Optional[str] = None,
        threshold: float = 0.8,
    ) -> Optional[Tuple]:
        """
        查找最佳匹配的卡牌

        Args:
            target_hash: 目标Hash值
            set_code: 指定系列代码，为None则全局搜索
            threshold: 相似度阈值

        Returns:
            - 系列模式 (set_code指定): (card_number, similarity)
            - 全局模式 (set_code=None): (set_code, card_number, similarity)
            - 无匹配: None
        """
        if set_code is None:
            return self._find_best_match_globally(target_hash, threshold)
        else:
            return self._find_best_match_in_series(set_code, target_hash, threshold)

    def _find_best_match_in_series(
        self, set_code: str, target_hash: np.ndarray, threshold: float
    ) -> Optional[Tuple[int, float]]:
        """在指定系列中查找最佳匹配"""
        if set_code not in self._series_cache:
            self._load_series_hash(set_code)

        series_hashes = self._series_cache.get(set_code, {})
        if not series_hashes:
            return None

        # 计算所有相似度，并按 (相似度降序, card_number升序) 排序
        # 确保相同卡面时优先选择编号较小的卡牌
        scored_items = [
            (card_number, calculate_similarity(target_hash, card_hash))
            for card_number, card_hash in series_hashes.items()
        ]

        # 排序规则：1. 相似度降序 2. 卡牌编号升序
        scored_items.sort(key=lambda x: (-x[1], x[0]))

        if scored_items and scored_items[0][1] >= threshold:
            return scored_items[0]

        return None

    def _apply_series_priority_sort(
        self,
        scored_items: List[Tuple],
        set_code_index: int = 0,
        similarity_index: int = 1,
    ) -> List[Tuple]:
        """
        应用系列优先级排序

        先按相似度降序排序，然后对于相似度差距小于 HASH_SIMILARITY_TIE_THRESHOLD 的候选，
        按系列号升序重新排序，确保相同卡面时优先选择系列号小的（如 A1 优先于 A4b）

        Args:
            scored_items: [(set_code, similarity, ...), ...] 或 [(similarity, set_code, ...), ...]
            set_code_index: set_code 在 tuple 中的索引位置
            similarity_index: similarity 在 tuple 中的索引位置

        Returns:
            排序后的列表
        """
        if not scored_items:
            return scored_items

        # 按相似度降序排序
        scored_items.sort(key=lambda x: -x[similarity_index])

        if len(scored_items) <= 1:
            return scored_items

        # 找出所有与最佳匹配差距在阈值内的候选
        best_sim = scored_items[0][similarity_index]
        tie_indices = [
            i
            for i, item in enumerate(scored_items)
            if best_sim - item[similarity_index] < HASH_SIMILARITY_TIE_THRESHOLD
        ]

        if len(tie_indices) <= 1:
            return scored_items

        # 对这些候选按 set_code 排序（提取、排序、替换）
        tie_candidates = [scored_items[i] for i in tie_indices]
        tie_candidates.sort(key=lambda x: x[set_code_index])

        # 替换回原位置
        for idx, tie_idx in enumerate(tie_indices):
            scored_items[tie_idx] = tie_candidates[idx]

        return scored_items

    def _find_best_match_globally(
        self, target_hash: np.ndarray, threshold: float
    ) -> Optional[Tuple[str, int, float]]:
        """在所有已加载系列中查找最佳匹配（跨系列检测）

        当多张卡牌相似度相同时，优先返回 set_code 较小的（字母序）
        当最佳与次佳匹配差距小于 HASH_SIMILARITY_TIE_THRESHOLD 时，优先选择系列号小的
        """
        # 确保全局索引已加载
        if not self._all_loaded:
            self.load_all_hashes()

        if not self._global_cache:
            return None

        # 计算所有相似度: (similarity, key)
        scored_items = [
            (calculate_similarity(target_hash, card_hash), key)
            for key, card_hash in self._global_cache.items()
        ]

        # 应用系列优先级排序
        scored_items = self._apply_series_priority_sort(
            scored_items, set_code_index=1, similarity_index=0
        )

        if not scored_items or scored_items[0][0] < threshold:
            return None

        best_similarity, best_key = scored_items[0]
        # 解析 key: "A1/001"
        set_code, card_number_str = best_key.split("/")
        card_number = int(card_number_str)
        return (set_code, card_number, best_similarity)

    def find_topk_candidates(
        self,
        target_hash: np.ndarray,
        set_code: Optional[str] = None,
        topk: int = TOPK_CANDIDATES,
        exclude_promo: bool = False,
    ) -> List[Tuple[str, int, float, np.ndarray]]:
        """
        查找TopK最佳匹配候选（用于两阶段匹配的第一阶段）

        Args:
            target_hash: 目标Hash值
            set_code: 指定系列代码，为None则全局搜索
            topk: 返回候选数量（默认从 constants 导入）
            exclude_promo: 全局模式时是否排除 PROMO 系列

        Returns:
            List[(set_code, card_number, similarity, hash_array), ...]
            按相似度降序排列的候选列表，包含完整hash用于第二阶段
        """
        # 获取待匹配的hash集合
        if set_code is None:
            # 全局模式
            # exclude_promo=True 时，避免触发包含 PROMO 的全量加载
            if exclude_promo:
                if not self._global_cache:
                    self.load_all_hashes(exclude_promo=True)
                source = {
                    key: hash_arr
                    for key, hash_arr in self._global_cache.items()
                    if not key.split("/", 1)[0].upper().startswith("PROMO")
                }
            else:
                if not self._all_loaded:
                    self.load_all_hashes()
                source = self._global_cache
            # 转换格式: "A1/001" -> (set_code, number, hash)
            items = [
                (key.split("/")[0], int(key.split("/")[1]), hash_arr)
                for key, hash_arr in source.items()
            ]
        else:
            # 系列模式
            if set_code not in self._series_cache:
                self._load_series_hash(set_code)
            series_data = self._series_cache.get(set_code, {})
            items = [
                (set_code, number, hash_arr) for number, hash_arr in series_data.items()
            ]

        if not items:
            return []

        # 计算所有相似度: (set_code, number, similarity, hash)
        scored_items = [
            (sc, num, calculate_similarity(target_hash, hash_arr), hash_arr)
            for sc, num, hash_arr in items
        ]

        # 应用系列优先级排序
        scored_items = self._apply_series_priority_sort(
            scored_items, set_code_index=0, similarity_index=2
        )

        return scored_items[:topk]

    def get_loaded_sets(self) -> Set[str]:
        """获取已加载的系列列表"""
        return self._loaded_sets.copy()

    def is_all_loaded(self) -> bool:
        """检查是否已加载所有系列"""
        return self._all_loaded

    def clear_failed_cache(self, set_code: Optional[str] = None) -> int:
        """
        强制刷新：清空下载失败缓存

        使用场景：当远程仓库补充了缺失的卡牌后，调用此方法重新尝试下载

        Args:
            set_code: 指定系列代码则只清空该系列的失败缓存，为None则清空全部

        Returns:
            清空的缓存条目数量
        """
        if set_code is None:
            count = len(self._failed_downloads)
            self._failed_downloads.clear()
            logger.info(f"已清空所有失败缓存（共 {count} 条）")
            return count
        else:
            # 只清空指定系列的失败缓存
            to_remove = {
                k for k in self._failed_downloads if k.startswith(f"{set_code}/")
            }
            for key in to_remove:
                self._failed_downloads.discard(key)
            logger.info(f"已清空系列 {set_code} 的失败缓存（共 {len(to_remove)} 条）")
            return len(to_remove)

    def get_failed_count(self, set_code: Optional[str] = None) -> int:
        """
        获取下载失败的卡牌数量

        Args:
            set_code: 指定系列代码则只统计该系列，为None则统计全部

        Returns:
            失败缓存条目数量
        """
        if set_code is None:
            return len(self._failed_downloads)
        else:
            return sum(
                1 for k in self._failed_downloads if k.startswith(f"{set_code}/")
            )


# 全局单例实例
_card_hash_manager_instance: Optional[CardHashManager] = None
_card_hash_manager_lock = threading.Lock()


def get_card_hash_manager() -> CardHashManager:
    """
    获取全局卡牌 Hash 管理器单例

    使用双重检查锁定确保线程安全。

    Returns:
        CardHashManager 单例实例
    """
    global _card_hash_manager_instance

    if _card_hash_manager_instance is None:
        with _card_hash_manager_lock:
            if _card_hash_manager_instance is None:
                _card_hash_manager_instance = CardHashManager()

    return _card_hash_manager_instance
