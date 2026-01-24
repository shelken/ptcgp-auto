# -*- coding: utf-8 -*-
"""
卡牌识别服务模块

负责在任务执行过程中识别屏幕上的卡牌。
封装了底层的截图和模板匹配逻辑，为任务层提供高层接口。
包含快速筛选（Quick Match）优化，以提高批量匹配性能。
"""

import logging
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from typing import List, Tuple, Dict, Optional

import cv2
import numpy as np
from PIL import Image

from ptcgp_auto_v2.infra.adb import AdbController
from ptcgp_auto_v2.infra.template import TemplateMatcher
from ptcgp_auto_v2.config.constants import DEFAULT_TEMPLATE_THRESHOLD, PACK_RESULT_ROI, PACK_RESULT_SCALE

logger = logging.getLogger(__name__)

# 快速匹配缩放比例
QUICK_MATCH_SCALE = 0.25
# 快速匹配容错缓冲 (主阈值 - 缓冲值)
QUICK_MATCH_THRESHOLD_BUFFER = 0.25


@dataclass
class RecognizedCard:
    """识别到的卡牌信息"""

    name: str
    confidence: float
    box: Tuple[int, int, int, int]
    # 未来可扩展: rarity, is_new, position 等


class CardRecognizer:
    """
    卡牌识别器

    协调 ADB 和 TemplateMatcher，执行卡牌识别任务。
    内部实现了 Quick Match 优化策略：
    1. 将屏幕和模板缩小 (0.25x)
    2. 进行粗略匹配筛选
    3. 对通过筛选的候选者进行原图精细匹配
    """

    def __init__(self, adb: AdbController, template_matcher: TemplateMatcher):
        self.adb = adb
        self.template_matcher = template_matcher
        # 线程池，用于并行匹配多个模板
        self.executor = ThreadPoolExecutor(max_workers=4)

    def _pil_to_cv2(self, pil_image: Image.Image) -> np.ndarray:
        """PIL Image 转 OpenCV 格式"""
        return cv2.cvtColor(np.array(pil_image), cv2.COLOR_RGB2BGR)

    def scan_pack_result(self) -> List[RecognizedCard]:
        """
        扫描开包结果页
        使用预定义的 ROI 区域进行识别，提高准确率并减少无关区域干扰
        """
        return self._analyze_screen(roi=PACK_RESULT_ROI, scale=PACK_RESULT_SCALE)

    def _analyze_screen(
        self,
        threshold: float = DEFAULT_TEMPLATE_THRESHOLD,
        scale: Optional[float] = None,
        roi: Optional[Tuple[int, int, int, int]] = None
    ) -> List[RecognizedCard]:
        """
        分析屏幕指定区域，识别其中的卡牌

        Args:
            threshold: 匹配置信度阈值
            scale: 模板缩放比例 (可选, 用于覆盖默认大小)
            roi: 感兴趣区域 (x, y, w, h)，基于 1080x1920 基准坐标

        Returns:
            识别到的卡牌列表 (坐标已还原为全屏坐标)
        """
        # 1. 获取截图
        screenshot = self.adb.screenshot()
        if not screenshot:
            logger.error("无法获取截图，跳过识别")
            return []

        # 2. 获取候选模板（仅限当前加载的卡包模板）
        candidate_templates = self.template_matcher._loaded_pack_templates
        if not candidate_templates:
            logger.warning("未加载任何卡包模板，无法进行识别")
            return []

        logger.info(f"开始识别卡牌 (候选模板数: {len(candidate_templates)})...")
        start_time = time.time()

        # 3. 准备图像数据 (Pre-processing)
        # 转换为 CV2 格式
        screen_cv = self._pil_to_cv2(screenshot)

        # 处理 ROI 裁剪
        crop_offset_x, crop_offset_y = 0, 0
        if roi:
            # ROI 是基于 1080x1920 的，需要根据实际分辨率缩放吗？
            # 假设 adb.screenshot() 返回的是实际分辨率，且 ROI 是基于基准分辨率定义的
            # 这里需要进行坐标转换
            # 但目前架构似乎假设 screenshot 已经是标准化或者我们在 CV 处理时自适应
            # 观察 adb.py，screenshot 返回原始分辨率。
            # 这里的 ROI 是常量 (1080p)，所以需要缩放 ROI 到实际屏幕尺寸

            # 获取当前屏幕尺寸
            h, w = screen_cv.shape[:2]
            base_w, base_h = 1080, 1920

            scale_x = w / base_w
            scale_y = h / base_h

            rx, ry, rw, rh = roi

            # 缩放 ROI
            scaled_rx = int(rx * scale_x)
            scaled_ry = int(ry * scale_y)
            scaled_rw = int(rw * scale_x)
            scaled_rh = int(rh * scale_y)

            # 裁剪
            screen_cv = screen_cv[scaled_ry:scaled_ry+scaled_rh, scaled_rx:scaled_rx+scaled_rw]
            crop_offset_x = scaled_rx
            crop_offset_y = scaled_ry

            # 如果裁剪后区域过小，无法匹配
            if screen_cv.shape[0] < 10 or screen_cv.shape[1] < 10:
                logger.error("ROI 裁剪后区域过小")
                return []

        # 准备缩略图用于快速筛选
        h, w = screen_cv.shape[:2]
        small_h, small_w = int(h * QUICK_MATCH_SCALE), int(w * QUICK_MATCH_SCALE)
        screen_small = cv2.resize(screen_cv, (small_w, small_h), interpolation=cv2.INTER_AREA)

        # 4. 并行执行匹配任务
        matches = []
        futures = {
            self.executor.submit(
                self._match_single_template,
                t_name,
                screen_cv,
                screen_small,
                threshold,
                scale
            ): t_name
            for t_name in candidate_templates
        }

        for future in as_completed(futures):
            t_name = futures[future]
            try:
                result = future.result()
                if result:
                    # 如果使用了 ROI，需要将局部坐标还原为全局坐标
                    if crop_offset_x > 0 or crop_offset_y > 0:
                        x1, y1, x2, y2 = result.box
                        result.box = (
                            x1 + crop_offset_x,
                            y1 + crop_offset_y,
                            x2 + crop_offset_x,
                            y2 + crop_offset_y
                        )
                    matches.append(result)
            except Exception as e:
                logger.error(f"模板匹配异常 {t_name}: {e}")

        # 5. 结果去重与排序
        # 按置信度降序排列
        matches.sort(key=lambda x: x.confidence, reverse=True)

        # 去除重叠 (NMS)
        final_cards = self._filter_overlapping(matches)

        duration = time.time() - start_time
        logger.info(
            f"识别完成，耗时 {duration:.2f}s, "
            f"扫描 {len(candidate_templates)} 个模板, "
            f"命中 {len(matches)}, 去重后 {len(final_cards)}"
        )

        return final_cards

    # 保留旧方法名以兼容（或直接废弃，但在本任务中我们只修改调用方）
    # 为了安全起见，可以保留一个别名，但 logic 已经移到 _analyze_screen
    def analyze_result_screen(self, threshold: float = DEFAULT_TEMPLATE_THRESHOLD, scale: Optional[float] = None) -> List[RecognizedCard]:
        return self._analyze_screen(threshold, scale)

    def _match_single_template(
        self,
        template_name: str,
        screen_cv: np.ndarray,
        screen_small: np.ndarray,
        threshold: float,
        scale: Optional[float] = None
    ) -> Optional[RecognizedCard]:
        """
        单个模板的匹配逻辑（包含 Quick Match 优化）

        Args:
            template_name: 模板名称
            screen_cv: 原图 (CV2)
            screen_small: 缩略图 (CV2)
            threshold: 目标阈值
            scale: 模板缩放比例
        """
        # 获取模板图像 (CV2)
        # 直接访问 TemplateMatcher 的缓存，避免重复加载
        template = self.template_matcher.templates.get(template_name)
        if template is None:
            return None

        # 如果指定了缩放比例，对模板进行缩放
        if scale is not None:
            h, w = template.shape[:2]
            new_w, new_h = int(w * scale), int(h * scale)
            # 使用 INTER_AREA 进行缩小，INTER_LINEAR/CUBIC 进行放大
            interpolation = cv2.INTER_AREA if scale < 1.0 else cv2.INTER_LINEAR
            template = cv2.resize(template, (new_w, new_h), interpolation=interpolation)

        # --- 阶段 1: 快速筛选 (Quick Match) ---
        # 如果模板尺寸允许，先进行缩小匹配
        t_h, t_w = template.shape[:2]
        small_t_h, small_t_w = int(t_h * QUICK_MATCH_SCALE), int(t_w * QUICK_MATCH_SCALE)

        if small_t_h > 0 and small_t_w > 0:
            tmpl_small = cv2.resize(template, (small_t_w, small_t_h), interpolation=cv2.INTER_AREA)

            # 确保小模板不大于小屏幕
            if tmpl_small.shape[0] <= screen_small.shape[0] and tmpl_small.shape[1] <= screen_small.shape[1]:
                res_small = cv2.matchTemplate(screen_small, tmpl_small, cv2.TM_CCOEFF_NORMED)
                _, max_val_small, _, _ = cv2.minMaxLoc(res_small)

                # 如果快速匹配的置信度远低于阈值，直接跳过
                if max_val_small < (threshold - QUICK_MATCH_THRESHOLD_BUFFER):
                    return None

        # --- 阶段 2: 精细匹配 (Fine Match) ---
        # 只有通过筛选的才进行原图匹配
        # 确保模板不大于屏幕
        if t_h > screen_cv.shape[0] or t_w > screen_cv.shape[1]:
            return None

        result = cv2.matchTemplate(screen_cv, template, cv2.TM_CCOEFF_NORMED)
        _, max_val, _, max_loc = cv2.minMaxLoc(result)

        if max_val >= threshold:
            x1, y1 = max_loc
            x2, y2 = x1 + t_w, y1 + t_h
            return RecognizedCard(
                name=template_name,
                confidence=max_val,
                box=(x1, y1, x2, y2)
            )

        return None

    def _filter_overlapping(self, cards: List[RecognizedCard], iou_threshold: float = 0.5) -> List[RecognizedCard]:
        """
        去除重叠的识别结果 (NMS 简化版)
        优先保留置信度高的结果
        """
        if not cards:
            return []

        keep = []
        # cards 已经按 confidence 降序排列 (调用前已排序)

        while cards:
            current = cards.pop(0)
            keep.append(current)

            # 过滤掉与 current 重叠度高的其余卡片
            rest = []
            for other in cards:
                if self._calculate_iou(current.box, other.box) < iou_threshold:
                    rest.append(other)
            cards = rest

        return keep

    def _calculate_iou(self, box1, box2) -> float:
        """计算两个框的 IoU (Intersection over Union)"""
        x1_min, y1_min, x1_max, y1_max = box1
        x2_min, y2_min, x2_max, y2_max = box2

        # 计算交集区域
        x_inter_min = max(x1_min, x2_min)
        y_inter_min = max(y1_min, y2_min)
        x_inter_max = min(x1_max, x2_max)
        y_inter_max = min(y1_max, y2_max)

        if x_inter_max <= x_inter_min or y_inter_max <= y_inter_min:
            return 0.0

        area_inter = (x_inter_max - x_inter_min) * (y_inter_max - y_inter_min)

        area1 = (x1_max - x1_min) * (y1_max - y1_min)
        area2 = (x2_max - x2_min) * (y2_max - y2_min)

        area_union = area1 + area2 - area_inter

        if area_union <= 0:
            return 0.0

        return area_inter / area_union
