"""
颜色检测相关能力
"""

from typing import Optional, Tuple, Dict

import cv2
import numpy as np
from PIL import Image

from ptcgp_auto import config
from ptcgp_auto.logger import get_logger
from ptcgp_auto.recognizer_parts.constants import COLORS, COLOR_STATES

logger = get_logger(__name__)


class ColorDetectorMixin:
    """颜色检测能力"""

    def check_color_ratio(
        self,
        screenshot: Image.Image,
        region: Tuple[int, int, int, int],
        hsv_lower: Tuple[int, int, int],
        hsv_upper: Tuple[int, int, int],
        threshold: float = 0.1,
    ) -> bool:
        """检测区域内指定颜色占比是否超过阈值"""
        x1, y1, x2, y2 = region
        img = self.pil_to_cv2(screenshot)

        height, width = img.shape[:2]
        x1, y1 = max(0, x1), max(0, y1)
        x2, y2 = min(width, x2), min(height, y2)

        if x2 <= x1 or y2 <= y1:
            logger.debug(f"[颜色] 无效区域: ({x1},{y1})-({x2},{y2})")
            return False

        roi = img[y1:y2, x1:x2]
        hsv = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)
        mask = cv2.inRange(hsv, np.array(hsv_lower), np.array(hsv_upper))
        ratio = np.count_nonzero(mask) / mask.size

        logger.debug(
            f"[颜色] 区域({x1},{y1})-({x2},{y2}) 占比={ratio:.2%} 阈值={threshold:.2%}"
        )

        return ratio >= threshold

    def check_green(
        self,
        screenshot: Image.Image,
        region: Tuple[int, int, int, int],
        threshold: float = 0.1,
    ) -> bool:
        """便捷方法：检测区域内是否有足够的绿色"""
        return self.check_color_ratio(
            screenshot,
            region,
            COLORS["green"]["lower"],
            COLORS["green"]["upper"],
            threshold,
        )

    def get_color_ratio(
        self,
        screenshot: Image.Image,
        region: Tuple[int, int, int, int],
        hsv_lower: Tuple[int, int, int],
        hsv_upper: Tuple[int, int, int],
    ) -> float:
        """获取区域内指定颜色的占比（用于调试）"""
        x1, y1, x2, y2 = region
        img = self.pil_to_cv2(screenshot)

        height, width = img.shape[:2]
        x1, y1 = max(0, x1), max(0, y1)
        x2, y2 = min(width, x2), min(height, y2)

        if x2 <= x1 or y2 <= y1:
            return 0.0

        roi = img[y1:y2, x1:x2]
        hsv = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)
        mask = cv2.inRange(hsv, np.array(hsv_lower), np.array(hsv_upper))
        return np.count_nonzero(mask) / mask.size

    def _calculate_color_region(
        self,
        anchor_box: Tuple[int, int, int, int],
        region_config: Dict,
    ) -> Tuple[int, int, int, int]:
        """根据锚点和配置计算颜色检测区域"""
        ax1, ay1, ax2, ay2 = anchor_box
        position = region_config["position"]
        offset = region_config["offset"]
        width = region_config["width"]
        height = region_config["height"]

        screen_w = config.SCREEN_WIDTH
        screen_h = config.SCREEN_HEIGHT
        offset_px = int(offset * screen_w)
        width_px = int(width * screen_w)
        height_px = int(height * screen_h)

        anchor_cy = (ay1 + ay2) // 2
        anchor_cx = (ax1 + ax2) // 2

        if position == "left":
            x2 = ax1 - offset_px
            x1 = x2 - width_px
            y1 = anchor_cy - height_px // 2
            y2 = anchor_cy + height_px // 2
        elif position == "right":
            x1 = ax2 + offset_px
            x2 = x1 + width_px
            y1 = anchor_cy - height_px // 2
            y2 = anchor_cy + height_px // 2
        elif position == "above":
            y2 = ay1 - offset_px
            y1 = y2 - height_px
            x1 = anchor_cx - width_px // 2
            x2 = anchor_cx + width_px // 2
        elif position == "below":
            y1 = ay2 + offset_px
            y2 = y1 + height_px
            x1 = anchor_cx - width_px // 2
            x2 = anchor_cx + width_px // 2
        else:
            raise ValueError(f"未知的位置: {position}")

        return (x1, y1, x2, y2)

    def check_state(self, screenshot: Image.Image, state_name: str) -> Optional[bool]:
        """根据 COLOR_STATES 配置检测状态"""
        if state_name not in COLOR_STATES:
            logger.warning(f"未知的状态配置: {state_name}")
            return None

        state_config = COLOR_STATES[state_name]
        locator = state_config["locator"]

        anchor_box = None
        if locator["type"] == "text_pattern":
            anchor_box = self.find_text_variants(screenshot, locator["key"])
        elif locator["type"] == "template":
            anchor_box = self.find_template(screenshot, locator["key"])
        else:
            logger.warning(f"未知的定位类型: {locator['type']}")
            return None

        if anchor_box is None:
            logger.debug(f"[状态] 无法定位 {state_name} 的锚点")
            return None

        color_region = self._calculate_color_region(
            anchor_box, state_config["color_region"]
        )

        color_name = state_config["color"]
        if color_name not in COLORS:
            logger.warning(f"未知的颜色: {color_name}")
            return None

        color_config = COLORS[color_name]

        result = self.check_color_ratio(
            screenshot,
            color_region,
            color_config["lower"],
            color_config["upper"],
            state_config["threshold"],
        )

        logger.debug(f"[状态] {state_name} = {result}")

        return result
