# -*- coding: utf-8 -*-
"""
YOLO + 感知哈希卡牌识别器

使用 YOLO 检测卡牌位置，通过感知哈希匹配识别卡牌。
实现两阶段匹配策略：
  1. 第一阶段：基础哈希匹配，快速筛选TopK候选
  2. 第二阶段（如需要）：多视角哈希重排序，提高准确性
"""

import logging
from collections.abc import Callable
from dataclasses import dataclass
from typing import List, Optional, Tuple

import cv2
import numpy as np
from PIL import Image

from ptcgp_auto_v2.config.constants import (
    DETECT_HASH_VARIANT_TOP_TRIMS,
    HASH_CROP_BOTTOM_RATIO,
    HASH_CROP_SIDE_RATIO,
    HASH_CROP_TOP_RATIO,
    HASH_SIMILARITY_GAP_MIN,
    HASH_SIMILARITY_THRESHOLD,
    OBB_INSET_RATIO,
    SECOND_STAGE_STAGE1_WEIGHT,
    SECOND_STAGE_STAGE2_WEIGHT,
    TOPK_CANDIDATES,
    YOLO_OBB_THRESHOLD,
)
from ptcgp_auto_v2.infra.adb import AdbController
from ptcgp_auto_v2.infra.card_hash_manager import CardHashManager
from ptcgp_auto_v2.infra.model_manager import ModelManager
from ptcgp_auto_v2.utils.perceptual_hash import (
    bgr_to_color_pixels,
    calculate_perceptual_hash,
    calculate_similarity,
)

logger = logging.getLogger(__name__)

UNKNOWN_CARD_NUMBER = -1  # 未匹配卡牌编号占位


@dataclass
class DetectedCard:
    """检测到的卡牌"""

    set_code: Optional[str]  # 系列代码（全局匹配时提供）
    card_number: int  # 卡牌编号
    confidence: float  # YOLO检测置信度
    similarity: float  # Hash匹配相似度
    bbox: Tuple[int, int, int, int]  # 边框坐标 (x1, y1, x2, y2)
    center: Tuple[float, float]  # 中心点坐标 (用于排序)


@dataclass
class CardDetectionInfo:
    """卡牌检测信息（内部使用，包含裁剪图像）"""

    index: int  # 检测序号
    confidence: float  # YOLO检测置信度
    cropped: np.ndarray  # 裁剪后的BGR图像
    bbox: Tuple[int, int, int, int]  # 边框坐标 (x1, y1, x2, y2)
    center: Tuple[float, float]  # 中心点坐标


@dataclass
class MatchCandidate:
    """匹配候选信息"""

    set_code: str  # 系列代码
    card_number: int  # 卡牌编号
    final_score: float  # 最终相似度分数
    stage1_score: float  # 第一阶段分数
    stage2_score: float  # 第二阶段分数（如适用）


class YoloCardRecognizer:
    """YOLO+Hash卡牌识别器 - 支持两阶段匹配"""

    # 默认阈值（从 constants.py 统一引用）
    DEFAULT_OBB_THRESHOLD = YOLO_OBB_THRESHOLD  # YOLO检测置信度阈值
    DEFAULT_SIMILARITY_THRESHOLD = HASH_SIMILARITY_THRESHOLD  # Hash匹配相似度阈值

    # 基准分辨率像素常量（基于1080x1920标准分辨率）
    BASE_TARGET_WIDTH = 480  # 透视变换后卡牌宽度基准值
    BASE_TARGET_HEIGHT = 670  # 透视变换后卡牌高度基准值
    BASE_ROW_THRESHOLD = 25  # 同一行卡牌Y坐标差异阈值基准值

    def __init__(
        self,
        adb: AdbController,
        model_manager: ModelManager,
        hash_manager: CardHashManager,
    ):
        self.adb = adb
        self.model_manager = model_manager
        self.hash_manager = hash_manager

    def scan_pack_result(
        self,
        set_code: str,
        obb_threshold: float = DEFAULT_OBB_THRESHOLD,
        similarity_threshold: float = DEFAULT_SIMILARITY_THRESHOLD,
        debug: bool = False,
    ) -> List[DetectedCard]:
        """扫描开包结果页，返回识别到的卡牌列表"""
        return self.scan(
            set_code=set_code,
            obb_threshold=obb_threshold,
            similarity_threshold=similarity_threshold,
            debug=debug,
        )

    def scan(
        self,
        set_code: Optional[str] = None,
        obb_threshold: float = DEFAULT_OBB_THRESHOLD,
        similarity_threshold: float = DEFAULT_SIMILARITY_THRESHOLD,
        debug: bool = False,
        resolve_name: Optional[Callable[[Optional[str], int], Optional[str]]] = None,
        exclude_promo: bool = False,
    ) -> List[DetectedCard]:
        """通用扫描接口，支持全局或指定系列

        Args:
            set_code: 指定系列代码，None 表示全局模式
            obb_threshold: YOLO 检测置信度阈值
            similarity_threshold: Hash 匹配相似度阈值
            debug: 是否输出调试信息
            resolve_name: 卡牌名称解析函数
            exclude_promo: 是否排除 PROMO 系列（开包场景使用）
        """
        results, total, _ = self._scan_common(
            set_code=set_code,
            obb_threshold=obb_threshold,
            similarity_threshold=similarity_threshold,
            debug=debug,
            resolve_name=resolve_name,
            exclude_promo=exclude_promo,
        )

        logger.info(f"识别完成: {len(results)}/{total} 张卡牌匹配成功")
        return results

    @staticmethod
    def _log_debug_details(
        detected: List[DetectedCard],
        unmatched: List[DetectedCard],
        resolve_name: Optional[Callable[[Optional[str], int], Optional[str]]] = None,
    ) -> None:
        """输出详细的调试日志"""
        if detected:
            logger.info("====== 识别到 %s 张卡牌 ======", len(detected))
            for idx, item in enumerate(detected, start=1):
                card_name = (
                    resolve_name(item.set_code, item.card_number)
                    if resolve_name
                    else None
                )
                name_suffix = f"{card_name}" if card_name else ""
                logger.info(
                    "  - #%s %s/%s-%s conf=%.2f sim=%.2f center=(%.1f, %.1f)",
                    idx,
                    item.set_code or "unknown",
                    item.card_number,
                    name_suffix,
                    item.confidence,
                    item.similarity,
                    item.center[0],
                    item.center[1],
                )

        if unmatched:
            logger.info("====== 未匹配 %s 张卡牌 ======", len(unmatched))
            for idx, item in enumerate(unmatched, start=1):
                card_number = item.card_number
                card_name = (
                    resolve_name(item.set_code, card_number)
                    if resolve_name and card_number != UNKNOWN_CARD_NUMBER
                    else None
                )
                name_suffix = f"{card_name}" if card_name else ""
                logger.info(
                    "  - #%s %s/%s-%s conf=%.2f sim=%.2f center=(%.1f, %.1f)",
                    idx,
                    item.set_code or "unknown",
                    card_number if card_number != UNKNOWN_CARD_NUMBER else "unknown",
                    name_suffix,
                    item.confidence,
                    item.similarity,
                    item.center[0],
                    item.center[1],
                )

    def _scan_common(
        self,
        set_code: Optional[str],
        obb_threshold: float,
        similarity_threshold: float,
        debug: bool,
        resolve_name: Optional[Callable[[Optional[str], int], Optional[str]]] = None,
        exclude_promo: bool = False,
    ) -> Tuple[List[DetectedCard], int, List[DetectedCard]]:
        """
        通用扫描内部逻辑 - 实现两阶段匹配

        第一阶段：基础哈希匹配，取TopK候选
        第二阶段（如需要）：多视角哈希重排序
        """
        # 1. 确保模型已加载
        if not self.model_manager.is_model_ready():
            logger.warning("YOLO模型尚未加载完成")
            return [], 0, []

        # 2. 确保Hash已就绪（exclude_promo=True 时排除 PROMO 系列）
        if set_code:
            if not self.hash_manager.ensure_series_ready(
                set_code, exclude_promo=exclude_promo
            ):
                logger.error(f"无法确保系列 {set_code} Hash就绪")
                return [], 0, []
        else:
            if not self.hash_manager.load_all_hashes(exclude_promo=exclude_promo):
                logger.error("无法加载全局Hash索引")
                return [], 0, []

        # 3. 截图
        screenshot = self.adb.screenshot()
        if not screenshot:
            logger.error("截图失败")
            return [], 0, []

        # 4. YOLO检测卡牌
        detected_cards = self._detect_cards(screenshot, obb_threshold)
        if not detected_cards:
            logger.debug("未检测到卡牌")
            return [], 0, []

        # 5. 两阶段匹配
        results: List[DetectedCard] = []
        unmatched: List[DetectedCard] = []

        for card_info in detected_cards:
            cropped = card_info.cropped

            # 计算基础哈希（第一阶段）
            base_hash = self._compute_hash_from_bgr(cropped)
            if base_hash is None:
                logger.debug(f"卡牌 #{card_info.index} 哈希计算失败")
                continue

            # 获取TopK候选（第一阶段）
            topk_candidates = self.hash_manager.find_topk_candidates(
                base_hash, set_code=set_code, topk=TOPK_CANDIDATES
            )

            if not topk_candidates:
                logger.debug(f"卡牌 #{card_info.index} 无候选匹配")
                unmatched.append(
                    DetectedCard(
                        set_code=set_code,
                        card_number=UNKNOWN_CARD_NUMBER,
                        confidence=card_info.confidence,
                        similarity=0.0,
                        bbox=card_info.bbox,
                        center=card_info.center,
                    )
                )
                continue

            # 检查第一阶段最佳分数
            stage1_best_score = topk_candidates[0][2]

            # 第一阶段通过（>=阈值），直接返回，跳过第二阶段
            if stage1_best_score >= similarity_threshold:
                match_set_code, match_card_number, _ = topk_candidates[0][:3]
                results.append(
                    DetectedCard(
                        set_code=match_set_code,
                        card_number=match_card_number,
                        confidence=card_info.confidence,
                        similarity=stage1_best_score,
                        bbox=card_info.bbox,
                        center=card_info.center,
                    )
                )
                if debug:
                    card_id = f"{match_set_code}/{match_card_number:03d}"
                    logger.info(
                        f"卡牌 #{card_info.index}: ✅ 第一阶段通过 - {card_id} (sim={stage1_best_score:.4f})"
                    )
            else:
                # 第一阶段未通过，进入第二阶段：多视角哈希重排序
                reranked = self._perform_second_stage(
                    cropped, topk_candidates, similarity_threshold
                )

                if reranked and reranked[0].final_score >= similarity_threshold:
                    best = reranked[0]
                    # 检查相似度差距
                    second_score = reranked[1].final_score if len(reranked) > 1 else 0.0
                    gap = best.final_score - second_score

                    if gap >= HASH_SIMILARITY_GAP_MIN:
                        results.append(
                            DetectedCard(
                                set_code=best.set_code,
                                card_number=best.card_number,
                                confidence=card_info.confidence,
                                similarity=best.final_score,
                                bbox=card_info.bbox,
                                center=card_info.center,
                            )
                        )
                        if debug:
                            card_id = f"{best.set_code}/{best.card_number:03d}"
                            logger.info(
                                f"卡牌 #{card_info.index}: ✅ 第二阶段通过 - {card_id} (sim={best.final_score:.4f}, gap={gap:.4f})"
                            )
                    else:
                        # 差距不足，拒绝匹配
                        unmatched.append(
                            DetectedCard(
                                set_code=best.set_code,
                                card_number=best.card_number,
                                confidence=card_info.confidence,
                                similarity=best.final_score,
                                bbox=card_info.bbox,
                                center=card_info.center,
                            )
                        )
                        if debug:
                            card_id = f"{best.set_code}/{best.card_number:03d}"
                            logger.info(
                                f"卡牌 #{card_info.index}: ❌ 差距不足 - {card_id} (gap={gap:.4f} < {HASH_SIMILARITY_GAP_MIN})"
                            )
                else:
                    # 第二阶段也未通过
                    best_candidate = reranked[0] if reranked else None
                    unmatched.append(
                        DetectedCard(
                            set_code=best_candidate.set_code
                            if best_candidate
                            else set_code,
                            card_number=best_candidate.card_number
                            if best_candidate
                            else UNKNOWN_CARD_NUMBER,
                            confidence=card_info.confidence,
                            similarity=best_candidate.final_score
                            if best_candidate
                            else 0.0,
                            bbox=card_info.bbox,
                            center=card_info.center,
                        )
                    )
                    if debug:
                        logger.info(f"卡牌 #{card_info.index}: ❌ 未通过两阶段匹配")

        results = self._sort_by_reading_order(results)
        if debug:
            self._log_debug_details(results, unmatched, resolve_name)
        return results, len(detected_cards), unmatched

    def _perform_second_stage(
        self,
        cropped: np.ndarray,
        topk_candidates: List[Tuple[str, int, float, np.ndarray]],
        similarity_threshold: float,
    ) -> List[MatchCandidate]:
        """
        执行第二阶段匹配：多视角哈希重排序

        Args:
            cropped: 裁剪后的卡牌图像(BGR)
            topk_candidates: 第一阶段的TopK候选 [(set_code, card_number, similarity, hash_array), ...]
            similarity_threshold: 相似度阈值

        Returns:
            重排序后的候选列表
        """
        # 构建检测卡图的多视角哈希
        detect_variants = self._build_detect_hash_variants(cropped)
        if not detect_variants:
            # 回退到基础哈希
            base_hash = self._compute_hash_from_bgr(cropped)
            if base_hash is not None:
                detect_variants = [base_hash]

        if not detect_variants:
            return []

        # 对TopK候选进行第二阶段重排序
        reranked: List[MatchCandidate] = []
        for sc, num, stage1_score, db_hash in topk_candidates:
            # 使用多视角哈希计算第二阶段分数
            stage2_score = max(
                calculate_similarity(variant, db_hash) for variant in detect_variants
            )

            # 加权融合
            final_score = (
                SECOND_STAGE_STAGE1_WEIGHT * stage1_score
                + SECOND_STAGE_STAGE2_WEIGHT * stage2_score
            )

            reranked.append(
                MatchCandidate(
                    set_code=sc,
                    card_number=num,
                    final_score=final_score,
                    stage1_score=stage1_score,
                    stage2_score=stage2_score,
                )
            )

        # 按最终分数降序排列
        reranked.sort(key=lambda x: x.final_score, reverse=True)
        return reranked

    @staticmethod
    def _order_obb_corners(corners: np.ndarray) -> np.ndarray:
        """
        将 OBB 四点统一为 [左上, 右上, 右下, 左下] 顺序

        算法：先按Y坐标排序分为上下两组，每组再按X坐标排序
        """
        y_sorted = corners[np.argsort(corners[:, 1])]
        top_two = y_sorted[:2]
        bottom_two = y_sorted[2:]
        top_two = top_two[np.argsort(top_two[:, 0])]
        bottom_two = bottom_two[np.argsort(bottom_two[:, 0])]
        tl, tr = top_two[0], top_two[1]
        bl, br = bottom_two[0], bottom_two[1]
        return np.array([tl, tr, br, bl], dtype=np.float32)

    @staticmethod
    def _inset_obb_corners(
        corners: np.ndarray, ratio: float = OBB_INSET_RATIO
    ) -> np.ndarray:
        """
        按中心点将 OBB 四点向内收缩

        Args:
            corners: 4x2的角点坐标数组
            ratio: 收缩比例（0.04表示向内收缩4%）

        Returns:
            收缩后的角点坐标
        """
        center = corners.mean(axis=0)
        return center + (corners - center) * (1.0 - ratio)

    @staticmethod
    def _trim_for_hash(
        image_bgr: np.ndarray,
        top_ratio: float = HASH_CROP_TOP_RATIO,
        bottom_ratio: float = HASH_CROP_BOTTOM_RATIO,
        side_ratio: float = HASH_CROP_SIDE_RATIO,
    ) -> np.ndarray:
        """
        哈希前对卡图做非对称裁剪

        用于去除卡牌边缘的边框、卡名等区域，提高哈希匹配的准确性
        """
        if image_bgr.size == 0:
            return image_bgr
        h, w = image_bgr.shape[:2]
        x1 = int(w * side_ratio)
        x2 = int(w * (1.0 - side_ratio))
        y1 = int(h * top_ratio)
        y2 = int(h * (1.0 - bottom_ratio))
        x1 = max(0, min(x1, w - 1))
        x2 = max(x1 + 1, min(x2, w))
        y1 = max(0, min(y1, h - 1))
        y2 = max(y1 + 1, min(y2, h))
        return image_bgr[y1:y2, x1:x2]

    @staticmethod
    def _compute_hash_from_bgr(image_bgr: np.ndarray) -> Optional[np.ndarray]:
        """从 BGR 图像计算感知哈希"""
        if image_bgr.size == 0:
            return None
        # 使用 bgr_to_color_pixels 直接转换
        color_pixels = bgr_to_color_pixels(image_bgr)
        return calculate_perceptual_hash(color_pixels)

    def _build_detect_hash_variants(self, image_bgr: np.ndarray) -> List[np.ndarray]:
        """
        构建检测卡图的多视角哈希

        使用不同的顶部裁剪比例生成多个哈希变体，用于第二阶段匹配
        """
        variants: List[np.ndarray] = []
        seen: set[bytes] = set()
        for top_trim in DETECT_HASH_VARIANT_TOP_TRIMS:
            trimmed = self._trim_for_hash(
                image_bgr,
                top_ratio=top_trim,
                bottom_ratio=HASH_CROP_BOTTOM_RATIO,
                side_ratio=HASH_CROP_SIDE_RATIO,
            )
            hash_arr = self._compute_hash_from_bgr(trimmed)
            if hash_arr is None:
                continue
            key = hash_arr.tobytes()
            if key in seen:
                continue
            seen.add(key)
            variants.append(hash_arr)
        return variants

    # 重复检测去重阈值（基于1080x1920标准分辨率）
    BASE_DUPLICATE_DISTANCE_THRESHOLD = 50  # 中心点距离小于此值认为是重复检测

    def _remove_duplicates(
        self, detected: List[CardDetectionInfo]
    ) -> List[CardDetectionInfo]:
        """
        去除重复检测结果（基于中心点距离）

        当YOLO检测到同一张卡多次时，保留置信度最高的那个
        注意：只去除相同坐标的重复检测，保留不同位置的真实重复卡
        """
        if len(detected) <= 1:
            return detected

        # 按置信度降序排列
        sorted_cards = sorted(detected, key=lambda x: x.confidence, reverse=True)

        unique_cards: List[CardDetectionInfo] = []
        distance_threshold = self.adb.scaled_y(self.BASE_DUPLICATE_DISTANCE_THRESHOLD)

        for card in sorted_cards:
            is_duplicate = False
            for unique in unique_cards:
                # 计算中心点距离
                dist = np.sqrt(
                    (card.center[0] - unique.center[0]) ** 2
                    + (card.center[1] - unique.center[1]) ** 2
                )
                if dist < distance_threshold:
                    is_duplicate = True
                    logger.debug(
                        f"检测到重复卡: #{card.index}(conf={card.confidence:.3f}) "
                        f"与 #{unique.index}(conf={unique.confidence:.3f}) "
                        f"距离={dist:.1f}px，已过滤"
                    )
                    break

            if not is_duplicate:
                unique_cards.append(card)

        # 按原始索引重新排序
        unique_cards.sort(key=lambda x: x.index)

        filtered_count = len(detected) - len(unique_cards)
        if filtered_count > 0:
            logger.info(f"已过滤 {filtered_count} 个重复检测")

        return unique_cards

    def _detect_cards(
        self, screenshot: Image.Image, conf_threshold: float
    ) -> List[CardDetectionInfo]:
        """
        使用YOLO检测卡牌位置

        优先使用旋转框(OBB)进行透视变换，获得更准确的卡牌图像
        """
        model = self.model_manager.get_model()
        if model is None:
            logger.warning("YOLO模型未就绪，跳过检测")
            return []

        # PIL -> numpy (BGR)
        img_array = np.array(screenshot)
        if len(img_array.shape) == 3 and img_array.shape[2] == 4:
            img_array = cv2.cvtColor(img_array, cv2.COLOR_RGBA2RGB)
        img_bgr = cv2.cvtColor(img_array, cv2.COLOR_RGB2BGR)

        # YOLO推理
        results = model(img_bgr, verbose=False)
        result = results[0]

        if result.obb is None or len(result.obb) == 0:
            return []

        detected: List[CardDetectionInfo] = []
        for i, obb in enumerate(result.obb):
            conf = float(obb.conf[0].item())

            if conf < conf_threshold:
                continue

            # 优先使用矩形框裁剪（YOLO已经过NMS，重复少）
            if hasattr(obb, "xyxy") and obb.xyxy is not None:
                x1, y1, x2, y2 = map(int, obb.xyxy[0])
                x1, y1 = max(0, x1), max(0, y1)
                x2, y2 = min(img_bgr.shape[1], x2), min(img_bgr.shape[0], y2)
                cropped = img_bgr[y1:y2, x1:x2]
                center_x = (x1 + x2) / 2
                center_y = (y1 + y2) / 2
            elif hasattr(obb, "xyxyxyxy") and obb.xyxyxyxy is not None:
                # 备用：使用旋转框透视变换
                xyxyxyxy = obb.xyxyxyxy[0].cpu().numpy().reshape(-1, 2)
                corners = self._order_obb_corners(xyxyxyxy.astype(np.float32))
                corners = self._inset_obb_corners(corners, OBB_INSET_RATIO)

                # 根据当前分辨率缩放基准尺寸
                target_w = self.adb.scaled_x(self.BASE_TARGET_WIDTH)
                target_h = self.adb.scaled_y(self.BASE_TARGET_HEIGHT)

                dst = np.array(
                    [[0, 0], [target_w, 0], [target_w, target_h], [0, target_h]],
                    dtype=np.float32,
                )
                matrix = cv2.getPerspectiveTransform(corners, dst)
                cropped = cv2.warpPerspective(img_bgr, matrix, (target_w, target_h))
                center_x = corners[:, 0].mean()
                center_y = corners[:, 1].mean()
                x1, y1 = int(corners[:, 0].min()), int(corners[:, 1].min())
                x2, y2 = int(corners[:, 0].max()), int(corners[:, 1].max())
            else:
                continue

            detected.append(
                CardDetectionInfo(
                    index=i + 1,
                    confidence=conf,
                    cropped=cropped,
                    bbox=(x1, y1, x2, y2),
                    center=(center_x, center_y),
                )
            )

        # 去重：相同坐标的检测（YOLO重复检测），保留置信度最高的
        # detected = self._remove_duplicates(detected)

        return detected

    def _sort_by_reading_order(self, cards: List[DetectedCard]) -> List[DetectedCard]:
        """按阅读顺序排序：从上到下，从左到右"""
        if not cards:
            return cards

        # 按Y坐标分组（同一行的卡牌Y坐标相近）
        sorted_by_y = sorted(cards, key=lambda c: c.center[1])

        rows = []
        current_row = [sorted_by_y[0]]
        row_threshold = self.adb.scaled_y(self.BASE_ROW_THRESHOLD)

        if logger.isEnabledFor(logging.DEBUG):
            logger.debug("row_threshold=%s", row_threshold)
            logger.debug(
                "sorted_by_y=%s",
                [(card.card_number, card.center) for card in sorted_by_y],
            )

        for card in sorted_by_y[1:]:
            if abs(card.center[1] - current_row[0].center[1]) < row_threshold:
                current_row.append(card)
            else:
                # 当前行结束，按X坐标排序并保存
                current_row.sort(key=lambda c: c.center[0])
                rows.append(current_row)
                if logger.isEnabledFor(logging.DEBUG):
                    logger.debug(
                        "row=%s",
                        [(card.card_number, card.center) for card in current_row],
                    )
                current_row = [card]

        # 处理最后一行
        if current_row:
            current_row.sort(key=lambda c: c.center[0])
            rows.append(current_row)
            if logger.isEnabledFor(logging.DEBUG):
                logger.debug(
                    "row=%s",
                    [(card.card_number, card.center) for card in current_row],
                )

        # 合并所有行
        result = []
        for row in rows:
            result.extend(row)

        return result
