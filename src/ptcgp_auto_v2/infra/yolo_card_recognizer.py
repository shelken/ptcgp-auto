# -*- coding: utf-8 -*-
"""
YOLO + 感知哈希卡牌识别器

使用 YOLO 检测卡牌位置，通过感知哈希匹配识别卡牌。
"""

import logging
from datetime import datetime
from pathlib import Path
from dataclasses import dataclass
from typing import List, Optional, Tuple

import cv2
import numpy as np
from PIL import Image

from ptcgp_auto_v2.config.constants import (
    YOLO_OBB_THRESHOLD,
    HASH_SIMILARITY_THRESHOLD,
)
from ptcgp_auto_v2.infra.adb import AdbController
from ptcgp_auto_v2.infra.model_manager import ModelManager
from ptcgp_auto_v2.infra.card_hash_manager import CardHashManager
from ptcgp_auto_v2.utils.perceptual_hash import (
    bgr_to_color_pixels,
    calculate_perceptual_hash,
)

logger = logging.getLogger(__name__)


@dataclass
class DetectedCard:
    """检测到的卡牌"""

    set_code: Optional[str]  # 系列代码（全局匹配时提供）
    card_number: int  # 卡牌编号
    confidence: float  # YOLO检测置信度
    similarity: float  # Hash匹配相似度
    bbox: Tuple[int, int, int, int]  # 边框坐标 (x1, y1, x2, y2)
    center: Tuple[float, float]  # 中心点坐标 (用于排序)


class YoloCardRecognizer:
    """YOLO+Hash卡牌识别器"""

    # 默认阈值（从 constants.py 统一引用）
    DEFAULT_OBB_THRESHOLD = YOLO_OBB_THRESHOLD  # YOLO检测置信度阈值
    DEFAULT_SIMILARITY_THRESHOLD = HASH_SIMILARITY_THRESHOLD  # Hash匹配相似度阈值

    # 基准分辨率像素常量（基于1080x1920标准分辨率）
    # 这些值来源于 yolo-card-training/scripts/test_massive_matching.py 测试验证
    BASE_TARGET_WIDTH = 480  # 透视变换后卡牌宽度基准值
    BASE_TARGET_HEIGHT = 670  # 透视变换后卡牌高度基准值
    BASE_ROW_THRESHOLD = 10  # 同一行卡牌Y坐标差异阈值基准值

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
    ) -> List[DetectedCard]:
        """扫描开包结果页，返回识别到的卡牌列表"""
        results, total = self._scan_common(
            set_code=set_code,
            obb_threshold=obb_threshold,
            similarity_threshold=similarity_threshold,
        )
        converted = [
            DetectedCard(
                set_code=set_code,
                card_number=item["card_number"],
                confidence=item["confidence"],
                similarity=item["similarity"],
                bbox=item["bbox"],
                center=item["center"],
            )
            for item in results
        ]
        converted = self._sort_by_reading_order(converted)
        logger.info(f"识别完成: {len(converted)}/{total} 张卡牌匹配成功")
        return converted

    def scan(
        self,
        set_code: Optional[str] = None,
        obb_threshold: float = DEFAULT_OBB_THRESHOLD,
        similarity_threshold: float = DEFAULT_SIMILARITY_THRESHOLD,
    ) -> List[DetectedCard]:
        """通用扫描接口，支持全局或指定系列"""
        results, total = self._scan_common(
            set_code=set_code,
            obb_threshold=obb_threshold,
            similarity_threshold=similarity_threshold,
        )
        converted = [
            DetectedCard(
                set_code=item["set_code"],
                card_number=item["card_number"],
                confidence=item["confidence"],
                similarity=item["similarity"],
                bbox=item["bbox"],
                center=item["center"],
            )
            for item in results
        ]
        converted = self._sort_by_reading_order(converted)
        logger.info(f"识别完成: {len(converted)}/{total} 张卡牌匹配成功")
        return converted

    def _scan_common(
        self,
        set_code: Optional[str],
        obb_threshold: float,
        similarity_threshold: float,
    ) -> Tuple[List[dict], int]:
        """通用扫描内部逻辑"""
        # 1. 确保模型已加载
        if not self.model_manager.is_model_ready():
            logger.warning("YOLO模型尚未加载完成")
            return [], 0

        # 2. 确保Hash已就绪
        if set_code:
            if not self.hash_manager.ensure_series_ready(set_code):
                logger.error(f"无法确保系列 {set_code} Hash就绪")
                return [], 0
        else:
            if not self.hash_manager.load_all_hashes():
                logger.error("无法加载全局Hash索引")
                return [], 0

        # 3. 截图
        screenshot = self.adb.screenshot()
        if not screenshot:
            logger.error("截图失败")
            return [], 0

        # 4. YOLO检测卡牌
        detected_cards = self._detect_cards(screenshot, obb_threshold)
        if not detected_cards:
            logger.debug("未检测到卡牌")
            return [], 0

        # 5. 对每张检测到的卡牌进行Hash匹配
        label = set_code or "global"
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_dir = Path("output") / "recognition_debug" / f"{label}_{timestamp}"
        output_dir.mkdir(parents=True, exist_ok=True)

        results = []
        for card_info in detected_cards:
            cropped = card_info["cropped"]

            color_pixels = bgr_to_color_pixels(cropped)
            card_hash = calculate_perceptual_hash(color_pixels)

            match_set_code: Optional[str] = None
            match_card_number: Optional[int] = None
            similarity = 0.0
            match = self.hash_manager.find_best_match(
                card_hash, set_code=set_code, threshold=0.0
            )

            if match:
                if set_code:
                    match_card_number, similarity = match
                    match_set_code = set_code
                else:
                    match_set_code, match_card_number, similarity = match

                if similarity >= similarity_threshold:
                    results.append(
                        {
                            "set_code": match_set_code,
                            "card_number": match_card_number,
                            "confidence": card_info["confidence"],
                            "similarity": similarity,
                            "bbox": card_info["bbox"],
                            "center": card_info["center"],
                        }
                    )
                else:
                    logger.debug(
                        "未匹配卡牌: best=%s/%s, sim=%.4f, threshold=%.4f",
                        match_set_code or "unknown",
                        match_card_number
                        if match_card_number is not None
                        else "unknown",
                        similarity,
                        similarity_threshold,
                    )
            else:
                logger.debug(
                    "未匹配卡牌: best=unknown, sim=0.0000, threshold=%.4f",
                    similarity_threshold,
                )

            save_name = "unknown"
            save_similarity = 0.0
            if match_set_code and match_card_number is not None:
                save_name = f"{match_set_code}_{match_card_number:03d}"
                save_similarity = similarity
            file_name = (
                f"card_{card_info['index']:02d}_best_{save_name}"
                f"_conf_{card_info['confidence']:.3f}_sim_{save_similarity:.4f}.png"
            )
            cv2.imwrite(str(output_dir / file_name), cropped)

        return results, len(detected_cards)

    def _detect_cards(
        self, screenshot: Image.Image, conf_threshold: float
    ) -> List[dict]:
        """使用YOLO检测卡牌位置"""
        model = self.model_manager.get_model()

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

        detected = []
        for i, obb in enumerate(result.obb):
            conf = float(obb.conf[0].item())

            if conf < conf_threshold:
                continue

            # 使用矩形框裁剪
            if hasattr(obb, "xyxy") and obb.xyxy is not None:
                x1, y1, x2, y2 = map(int, obb.xyxy[0])
                x1, y1 = max(0, x1), max(0, y1)
                x2, y2 = min(img_bgr.shape[1], x2), min(img_bgr.shape[0], y2)
                cropped = img_bgr[y1:y2, x1:x2]
                center_x = (x1 + x2) / 2
                center_y = (y1 + y2) / 2
            else:
                # 备用：使用旋转框透视变换
                xyxyxyxy = obb.xyxyxyxy[0].cpu().numpy().reshape(-1, 2)
                corners = xyxyxyxy.astype(np.float32)

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

            detected.append(
                {
                    "index": i + 1,
                    "confidence": conf,
                    "cropped": cropped,
                    "bbox": (x1, y1, x2, y2),
                    "center": (center_x, center_y),
                }
            )

        return detected

    def _sort_by_reading_order(self, cards: List[DetectedCard]) -> List[DetectedCard]:
        """按阅读顺序排序：从上到下，从左到右"""
        if not cards:
            return cards

        # 按Y坐标分组（同一行的卡牌Y坐标相近）
        sorted_by_y = sorted(cards, key=lambda c: c.center[1])

        rows = []
        current_row = [sorted_by_y[0]]
        # 根据当前分辨率缩放行阈值（基准100px对应1080x1920）
        row_threshold = self.adb.scaled_y(self.BASE_ROW_THRESHOLD)

        for card in sorted_by_y[1:]:
            if abs(card.center[1] - current_row[0].center[1]) < row_threshold:
                current_row.append(card)
            else:
                # 当前行结束，按X坐标排序并保存
                current_row.sort(key=lambda c: c.center[0])
                rows.append(current_row)
                current_row = [card]

        # 处理最后一行
        if current_row:
            current_row.sort(key=lambda c: c.center[0])
            rows.append(current_row)

        # 合并所有行
        result = []
        for row in rows:
            result.extend(row)

        return result
