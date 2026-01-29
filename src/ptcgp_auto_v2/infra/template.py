# -*- coding: utf-8 -*-
"""
模板匹配模块

使用 OpenCV 进行图像模板匹配。
"""

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import cv2
import numpy as np
from PIL import Image

from ptcgp_auto_v2.config.constants import DEFAULT_TEMPLATE_THRESHOLD, TEMPLATE_BASE_WIDTH
from ptcgp_auto_v2.utils.card_naming import normalize_name_str

logger = logging.getLogger(__name__)

# 定义比 DEBUG(10) 更低的日志级别
TRACE = 5


@dataclass
class TemplateMatch:
    """模板匹配结果"""

    template_name: str
    box: Tuple[int, int, int, int]  # (x1, y1, x2, y2)
    confidence: float

    def to_dict(self) -> dict:
        """转换为字典格式"""
        return {
            "template": self.template_name,
            "box": self.box,
            "confidence": self.confidence,
        }


class TemplateMatcher:
    """
    模板匹配器

    使用 OpenCV 进行模板匹配，支持自动缩放。
    """

    def __init__(
        self,
        templates_dir: str = "templates",
        threshold: float = DEFAULT_TEMPLATE_THRESHOLD,
        base_width: int = TEMPLATE_BASE_WIDTH,
    ):
        """
        初始化模板匹配器

        Args:
            templates_dir: 模板图片目录
            threshold: 匹配阈值
            base_width: 模板图片的基准宽度
        """
        self.templates_dir = Path(templates_dir)
        self.threshold = threshold
        self.base_width = base_width
        self.templates: Dict[str, np.ndarray] = {}
        self._core_loaded = False  # 标记核心模板是否已加载
        self._current_scale = 1.0
        self._screen_width: Optional[int] = None  # 当前设备分辨率宽度
        # 记录已加载的附加模板（用于卸载）
        self._loaded_pack_templates: List[str] = []

    def set_screen_width(self, width: int):
        """
        设置当前屏幕宽度并更新缩放比例

        Args:
            width: 屏幕宽度
        """
        if self._screen_width == width:
            return

        self._screen_width = width
        self._current_scale = width / self.base_width
        logger.debug(
            f"设置模板缩放比例: {self._current_scale:.2f} "
            f"({width}/{self.base_width})"
        )

        # 如果比例发生变化且已加载了模板，可能需要清空或重新缩放
        # 为简单起见，如果 scale 变化显著，我们清空当前模板以强制重新加载
        # 但我们保留附加模板列表，以便知道哪些是 pack 模板（虽然它们也被清除了）
        # 这里只清空 self.templates，_loaded_pack_templates 仅用于记录名称
        # 更好的做法可能是重新加载所有已知的模板，但这里我们假设调用方会按需重新加载
        if self.templates:
            logger.debug("缩放比例变化，清空已加载模板")
            self.templates.clear()
            self._core_loaded = False
            self._loaded_pack_templates.clear()  # 它们也没了

    def _normalize_name(self, name: str) -> str:
        """规范化模板名称：移除 .png 后缀"""
        if name.endswith(".png"):
            return name[:-4]
        return name

    def _pil_to_cv2(self, pil_image: Image.Image) -> np.ndarray:
        """PIL Image 转 OpenCV 格式"""
        return cv2.cvtColor(np.array(pil_image), cv2.COLOR_RGB2BGR)

    def load_core_templates(self, screen_width: Optional[int] = None):
        """
        加载核心模板图片（不包含 cards/ 目录下的卡牌图片）

        不清除现有模板（如卡包模板），只增量加载核心模板。

        Args:
            screen_width: 当前屏幕宽度（可选，若提供则更新缩放比例）
        """
        if screen_width:
            self.set_screen_width(screen_width)

        if self._core_loaded:
            return

        if not self.templates_dir.exists():
            logger.warning(f"模板目录不存在: {self.templates_dir}")
            return

        count = 0
        for file in self.templates_dir.glob("**/*.png"):
            # 使用相对路径判断是否在 cards 目录下
            rel_path = file.relative_to(self.templates_dir)
            if str(rel_path).startswith("cards"):
                continue

            if self._load_template_file(file):
                count += 1

        logger.debug(f"加载核心模板: {count} 个")
        self._core_loaded = True

    # 兼容旧接口
    def load_templates(self, screen_width: int = TEMPLATE_BASE_WIDTH):
        self.load_core_templates(screen_width)

    def load_pack_templates(self, pack_code: str, booster_name: Optional[str] = None) -> int:
        """
        加载指定卡包的模板（卡牌图片）

        Args:
            pack_code: 卡包代码，如 "A1"
            booster_name: 子包名称，如 "Charizard" (可选，若不传则加载该系列下所有卡牌)

        Returns:
            加载数量
        """
        # 路径规则: cards/{pack_code}[/{booster_name_safe}]
        sub_dir = f"cards/{pack_code}"

        if booster_name:
            # 确保空格被替换为下划线
            safe_booster = normalize_name_str(booster_name)
            sub_dir = f"{sub_dir}/{safe_booster}"

        target_dir = self.templates_dir / sub_dir
        if not target_dir.exists():
            logger.warning(f"卡包模板目录不存在: {target_dir}")
            return 0

        count = 0
        for file in target_dir.glob("**/*.png"):
            if self._load_template_file(file, is_pack_template=True):
                count += 1

        label = f"{pack_code}/{booster_name}" if booster_name else f"{pack_code}(All)"
        logger.debug(f"加载卡包模板 {label}: {count} 个")
        return count

    def unload_pack_templates(self):
        """卸载所有已加载的卡包模板，释放内存"""
        if not self._loaded_pack_templates:
            return

        count = 0
        for name in self._loaded_pack_templates:
            if name in self.templates:
                del self.templates[name]
                count += 1

        self._loaded_pack_templates.clear()
        logger.debug(f"已卸载 {count} 个卡包模板")

    def load_additional_templates(self, sub_dir: str):
        """
        加载指定子目录的模板（增量加载）

        Args:
            sub_dir: 相对于 templates 的子目录，如 "cards/A1/Charizard"
        """
        target_dir = self.templates_dir / sub_dir
        if not target_dir.exists():
            logger.warning(f"附加模板目录不存在: {target_dir}")
            return

        count = 0
        for file in target_dir.glob("**/*.png"):
            if self._load_template_file(file):
                count += 1

        logger.debug(f"加载附加模板 {sub_dir}: {count} 个")

    def _load_template_file(self, file_path: Path, is_pack_template: bool = False) -> bool:
        """加载单个模板文件"""
        try:
            # 使用相对路径作为模板名（支持子目录）
            rel_path = file_path.relative_to(self.templates_dir)
            name = str(rel_path.with_suffix(""))

            # 如果已存在，跳过（避免重复加载）
            if name in self.templates:
                return False

            img = cv2.imread(str(file_path))
            if img is None:
                return False

            # 按屏幕比例缩放
            if abs(self._current_scale - 1.0) > 0.01:
                new_w = int(img.shape[1] * self._current_scale)
                new_h = int(img.shape[0] * self._current_scale)
                img = cv2.resize(img, (new_w, new_h), interpolation=cv2.INTER_AREA)

            self.templates[name] = img
            if is_pack_template:
                self._loaded_pack_templates.append(name)
            return True
        except Exception as e:
            logger.error(f"加载模板失败 {file_path}: {e}")
            return False

    def _ensure_templates_loaded(self):
        """确保核心模板已加载"""
        if not self._core_loaded:
            self.load_core_templates()

    def _load_core_templates_only(self):
        """已弃用，使用 load_core_templates"""
        self.load_core_templates()

    def find(
        self,
        screenshot: Image.Image,
        template_name: str,
        threshold: Optional[float] = None,
    ) -> Optional[TemplateMatch]:
        """
        在截图中查找模板

        Args:
            screenshot: PIL Image 截图
            template_name: 模板名称
            threshold: 匹配阈值（可选，默认使用实例阈值）

        Returns:
            TemplateMatch 或 None
        """
        self._ensure_templates_loaded()

        template_name = self._normalize_name(template_name)
        if template_name not in self.templates:
            logger.debug(f"模板不存在: {template_name}")
            return None

        threshold = threshold or self.threshold
        template = self.templates[template_name]
        screen = self._pil_to_cv2(screenshot)

        result = cv2.matchTemplate(screen, template, cv2.TM_CCOEFF_NORMED)
        min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(result)

        if max_val >= threshold:
            h, w = template.shape[:2]
            x1, y1 = max_loc
            x2, y2 = x1 + w, y1 + h

            logger.debug(
                f"[模板] 找到 {template_name}: "
                f"({x1},{y1})-({x2},{y2}) 置信度={max_val:.2f}"
            )

            return TemplateMatch(
                template_name=template_name,
                box=(x1, y1, x2, y2),
                confidence=max_val,
            )

        # 使用 TRACE 级别 (5) 记录未找到的日志，避免刷屏
        logger.log(
            TRACE,
            f"[模板] 未找到 {template_name}, 最高置信度={max_val:.2f} "
            f"(阈值={threshold})",
        )
        return None

    def find_box(
        self,
        screenshot: Image.Image,
        template_name: str,
        threshold: Optional[float] = None,
    ) -> Optional[Tuple[int, int, int, int]]:
        """
        在截图中查找模板，返回边界框

        Args:
            screenshot: PIL Image 截图
            template_name: 模板名称
            threshold: 匹配阈值

        Returns:
            (x1, y1, x2, y2) 或 None
        """
        match = self.find(screenshot, template_name, threshold)
        return match.box if match else None

    def get_confidence(
        self,
        screenshot: Image.Image,
        template_name: str,
    ) -> float:
        """
        获取模板匹配的最高置信度

        Args:
            screenshot: PIL Image 截图
            template_name: 模板名称

        Returns:
            置信度值（0.0-1.0）
        """
        self._ensure_templates_loaded()

        template_name = self._normalize_name(template_name)
        if template_name not in self.templates:
            return 0.0

        template = self.templates[template_name]
        screen = self._pil_to_cv2(screenshot)

        result = cv2.matchTemplate(screen, template, cv2.TM_CCOEFF_NORMED)
        _, max_val, _, _ = cv2.minMaxLoc(result)

        return max_val

    def find_all(
        self,
        screenshot: Image.Image,
        template_name: str,
        threshold: Optional[float] = None,
        scale: float = 1.0
    ) -> List[TemplateMatch]:
        """
        在截图中查找所有匹配的模板

        Args:
            screenshot: PIL Image 截图
            template_name: 模板名称
            threshold: 匹配阈值

        Returns:
            TemplateMatch 列表
        """
        self._ensure_templates_loaded()

        template_name = self._normalize_name(template_name)
        if template_name not in self.templates:
            logger.warning(f"模板不存在: {template_name}")
            return []

        threshold = threshold or self.threshold
        template = self.templates[template_name]
        screen = self._pil_to_cv2(screenshot)

        # 缩放模板
        if abs(scale - 1.0) > 0.01:
            new_w = int(template.shape[1] * scale)
            new_h = int(template.shape[0] * scale)
            logger.debug(f"模板缩放后: {new_w} x {new_h}")
            template = cv2.resize(
                template, (new_w, new_h), interpolation=cv2.INTER_AREA
            )

        result = cv2.matchTemplate(screen, template, cv2.TM_CCOEFF_NORMED)
        locations = np.where(result >= threshold)

        h, w = template.shape[:2]
        boxes = []

        for pt in zip(*locations[::-1]):
            x1, y1 = pt
            x2, y2 = x1 + w, y1 + h
            confidence = result[y1, x1]
            boxes.append((x1, y1, x2, y2, confidence))

        # 非极大值抑制
        filtered = self._non_max_suppression(boxes)

        matches = [
            TemplateMatch(
                template_name=template_name,
                box=(x1, y1, x2, y2),
                confidence=conf,
            )
            for x1, y1, x2, y2, conf in filtered
        ]

        logger.debug(f"找到 {len(matches)} 个 {template_name}")
        return matches

    def _non_max_suppression(
        self,
        boxes: List[Tuple[int, int, int, int, float]],
        overlap_thresh: float = 0.5,
    ) -> List[Tuple[int, int, int, int, float]]:
        """
        非极大值抑制，去除重叠的检测框

        Args:
            boxes: [(x1, y1, x2, y2, confidence), ...]
            overlap_thresh: 重叠阈值

        Returns:
            过滤后的框列表
        """
        if len(boxes) == 0:
            return []

        boxes_array = np.array(boxes)
        x1 = boxes_array[:, 0]
        y1 = boxes_array[:, 1]
        x2 = boxes_array[:, 2]
        y2 = boxes_array[:, 3]
        confidences = boxes_array[:, 4]

        areas = (x2 - x1) * (y2 - y1)
        indices = np.argsort(confidences)

        keep = []
        while len(indices) > 0:
            last = len(indices) - 1
            i = indices[last]
            keep.append(i)

            xx1 = np.maximum(x1[i], x1[indices[:last]])
            yy1 = np.maximum(y1[i], y1[indices[:last]])
            xx2 = np.minimum(x2[i], x2[indices[:last]])
            yy2 = np.minimum(y2[i], y2[indices[:last]])

            w = np.maximum(0, xx2 - xx1)
            h = np.maximum(0, yy2 - yy1)

            overlap = (w * h) / areas[indices[:last]]

            indices = np.delete(
                indices,
                np.concatenate(([last], np.where(overlap > overlap_thresh)[0])),
            )

        return [tuple(boxes_array[i]) for i in keep]

    def find_with_scale(
        self,
        screenshot: Image.Image,
        template_name: str,
        scale: float,
        threshold: Optional[float] = None,
    ) -> Optional[TemplateMatch]:
        """
        按指定缩放比例匹配模板

        Args:
            screenshot: PIL Image 截图
            template_name: 模板名称
            scale: 缩放比例
            threshold: 匹配阈值

        Returns:
            TemplateMatch 或 None
        """
        self._ensure_templates_loaded()

        template_name = self._normalize_name(template_name)
        if template_name not in self.templates:
            logger.debug(f"模板不存在: {template_name}")
            return None

        threshold = threshold or self.threshold
        template = self.templates[template_name]

        # 缩放模板
        if abs(scale - 1.0) > 0.01:
            new_w = int(template.shape[1] * scale)
            new_h = int(template.shape[0] * scale)
            template = cv2.resize(
                template, (new_w, new_h), interpolation=cv2.INTER_AREA
            )

        screen = self._pil_to_cv2(screenshot)

        # 检查模板不能大于截图
        if template.shape[0] > screen.shape[0] or template.shape[1] > screen.shape[1]:
            logger.debug(f"模板尺寸 ({template.shape[1]}x{template.shape[0]}) 大于截图")
            return None

        result = cv2.matchTemplate(screen, template, cv2.TM_CCOEFF_NORMED)
        _, max_val, _, max_loc = cv2.minMaxLoc(result)

        if max_val >= threshold:
            h, w = template.shape[:2]
            x1, y1 = max_loc
            x2, y2 = x1 + w, y1 + h

            logger.debug(
                f"[模板@{scale:.2f}] 找到 {template_name}: "
                f"({x1},{y1})-({x2},{y2}) 置信度={max_val:.2f}"
            )

            return TemplateMatch(
                template_name=template_name,
                box=(x1, y1, x2, y2),
                confidence=max_val,
            )

        logger.debug(
            f"[模板@{scale:.2f}] 未找到 {template_name}, 最高置信度={max_val:.2f}"
        )
        return None
