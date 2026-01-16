"""
模板匹配相关能力
"""

from pathlib import Path
from typing import Optional, Tuple, List, Dict

import cv2
import numpy as np
from PIL import Image

from ptcgp_auto import config
from ptcgp_auto.logger import get_logger

logger = get_logger(__name__)


def _normalize_template_name(name: str) -> str:
    """规范化模板名称：移除 .png 后缀"""
    if name.endswith(".png"):
        return name[:-4]
    return name


class TemplateMatcherMixin:
    """模板匹配能力"""

    templates_dir: Path
    templates: Dict[str, np.ndarray]

    def reload_templates(self):
        """重新加载模板（根据当前分辨率缩放）"""
        self.templates.clear()
        self._load_templates()

    def _load_templates(self):
        """加载所有模板图片，并根据当前分辨率缩放"""
        if not self.templates_dir.exists():
            logger.warning(f"模板目录不存在: {self.templates_dir}")
            return

        scale = config.SCREEN_WIDTH / config.TEMPLATE_BASE_WIDTH
        if abs(scale - 1.0) > 0.01:
            logger.info(
                f"模板缩放比例: {scale:.2f} "
                f"({config.SCREEN_WIDTH}/{config.TEMPLATE_BASE_WIDTH})"
            )

        for file in self.templates_dir.glob("**/*.png"):
            # 使用相对路径作为模板名（支持子目录）
            rel_path = file.relative_to(self.templates_dir)
            name = str(rel_path.with_suffix(""))  # 移除 .png 后缀
            img = cv2.imread(str(file))
            if img is not None:
                if abs(scale - 1.0) > 0.01:
                    new_w = int(img.shape[1] * scale)
                    new_h = int(img.shape[0] * scale)
                    img = cv2.resize(img, (new_w, new_h), interpolation=cv2.INTER_AREA)
                self.templates[name] = img
                logger.info(f"已加载模板: {name}")

    def pil_to_cv2(self, pil_image: Image.Image) -> np.ndarray:
        """PIL Image 转 OpenCV 格式"""
        return cv2.cvtColor(np.array(pil_image), cv2.COLOR_RGB2BGR)

    def find_template(
        self,
        screenshot: Image.Image,
        template_name: str,
        threshold: float = None,
    ) -> Optional[Tuple[int, int, int, int]]:
        """在截图中查找模板"""
        if not self.templates:
            self._load_templates()

        # 规范化模板名称
        template_name = _normalize_template_name(template_name)

        if template_name not in self.templates:
            logger.debug(f"模板不存在: {template_name}")
            return None

        threshold = threshold or config.TEMPLATE_THRESHOLD
        template = self.templates[template_name]
        screen = self.pil_to_cv2(screenshot)

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

            return (x1, y1, x2, y2)

        logger.debug(
            f"[模板] 未找到 {template_name}, 最高置信度={max_val:.2f} "
            f"(阈值={threshold})"
        )
        return None

    def get_template_confidence(
        self,
        screenshot: Image.Image,
        template_name: str,
    ) -> float:
        """获取模板匹配的最高置信度（不考虑阈值）"""
        if not self.templates:
            self._load_templates()

        # 规范化模板名称
        template_name = _normalize_template_name(template_name)

        if template_name not in self.templates:
            return 0.0

        template = self.templates[template_name]
        screen = self.pil_to_cv2(screenshot)

        result = cv2.matchTemplate(screen, template, cv2.TM_CCOEFF_NORMED)
        _, max_val, _, _ = cv2.minMaxLoc(result)

        return max_val

    def find_template_at_scale(
        self,
        screenshot: Image.Image,
        template_name: str,
        scale: float,
        threshold: float = None,
    ) -> Optional[Tuple[int, int, int, int]]:
        """
        按指定缩放比例匹配模板

        Args:
            screenshot: 截图
            template_name: 模板名称
            scale: 缩放比例 (0.35 = 缩小到 35%)
            threshold: 匹配阈值

        Returns:
            匹配框 (x1, y1, x2, y2) 或 None
        """
        if not self.templates:
            self._load_templates()

        template_name = _normalize_template_name(template_name)
        if template_name not in self.templates:
            logger.debug(f"模板不存在: {template_name}")
            return None

        threshold = threshold or config.TEMPLATE_THRESHOLD
        template = self.templates[template_name]

        # 缩放模板
        if abs(scale - 1.0) > 0.01:
            new_w = int(template.shape[1] * scale)
            new_h = int(template.shape[0] * scale)
            template = cv2.resize(template, (new_w, new_h), interpolation=cv2.INTER_AREA)

        screen = self.pil_to_cv2(screenshot)

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

            return (x1, y1, x2, y2)

        logger.debug(
            f"[模板@{scale:.2f}] 未找到 {template_name}, 最高置信度={max_val:.2f}"
        )
        return None

    def get_template_confidence_at_scale(
        self,
        screenshot: Image.Image,
        template_name: str,
        scale: float,
    ) -> float:
        """获取指定缩放比例下的匹配置信度"""
        if not self.templates:
            self._load_templates()

        template_name = _normalize_template_name(template_name)
        if template_name not in self.templates:
            return 0.0

        template = self.templates[template_name]

        # 缩放模板
        if abs(scale - 1.0) > 0.01:
            new_w = int(template.shape[1] * scale)
            new_h = int(template.shape[0] * scale)
            template = cv2.resize(template, (new_w, new_h), interpolation=cv2.INTER_AREA)

        screen = self.pil_to_cv2(screenshot)

        # 检查模板不能大于截图
        if template.shape[0] > screen.shape[0] or template.shape[1] > screen.shape[1]:
            return 0.0

        result = cv2.matchTemplate(screen, template, cv2.TM_CCOEFF_NORMED)
        _, max_val, _, _ = cv2.minMaxLoc(result)

        return max_val

    def find_all_templates(
        self,
        screenshot: Image.Image,
        template_name: str,
        threshold: float = None,
    ) -> List[Tuple[int, int, int, int]]:
        """在截图中查找所有匹配的模板"""
        if not self.templates:
            self._load_templates()

        # 规范化模板名称
        template_name = _normalize_template_name(template_name)

        if template_name not in self.templates:
            logger.warning(f"模板不存在: {template_name}")
            return []

        threshold = threshold or config.TEMPLATE_THRESHOLD
        template = self.templates[template_name]
        screen = self.pil_to_cv2(screenshot)

        result = cv2.matchTemplate(screen, template, cv2.TM_CCOEFF_NORMED)
        locations = np.where(result >= threshold)

        h, w = template.shape[:2]
        boxes = []

        for pt in zip(*locations[::-1]):
            x1, y1 = pt
            x2, y2 = x1 + w, y1 + h
            boxes.append((x1, y1, x2, y2))

        boxes = self._non_max_suppression(boxes)

        logger.debug(f"找到 {len(boxes)} 个 {template_name}")

        return boxes

    def _non_max_suppression(
        self,
        boxes: List[Tuple[int, int, int, int]],
        overlap_thresh: float = 0.5,
    ) -> List[Tuple[int, int, int, int]]:
        """非极大值抑制，去除重叠的检测框"""
        if len(boxes) == 0:
            return []

        boxes_array = np.array(boxes)
        x1 = boxes_array[:, 0]
        y1 = boxes_array[:, 1]
        x2 = boxes_array[:, 2]
        y2 = boxes_array[:, 3]

        areas = (x2 - x1) * (y2 - y1)
        indices = np.argsort(y1)

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

        return [boxes[i] for i in keep]
