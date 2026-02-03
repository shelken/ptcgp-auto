# -*- coding: utf-8 -*-
"""
调试可视化工具模块

提供在 Debug 模式下生成和展示识别结果图片的功能。
支持检测 Kitty 终端并直接在终端内显示图片。
"""

import logging
import time
from pathlib import Path
from typing import Any, List, Optional, Tuple, Union

import cv2
import numpy as np
from PIL import Image

from ptcgp_auto_v2.config.settings import get_settings
from ptcgp_auto_v2.utils.terminal_preview import _is_kitty, preview_image_inline

logger = logging.getLogger(__name__)


class DebugVisualizer:
    """调试可视化工具"""

    @staticmethod
    def is_kitty() -> bool:
        """检测是否在 Kitty 终端中运行"""
        return _is_kitty()

    @staticmethod
    def show_in_kitty(image: Union[str, Path, Image.Image]):
        """在 Kitty 终端直接显示图片"""
        # 使用 inline 模式，让图片随文本滚动，避免遮挡
        preview_image_inline(image)

    @staticmethod
    def draw_recognition_result(
        image: np.ndarray,
        roi: Optional[Tuple[int, int, int, int]],
        cards: List[Any],
        filename_prefix: str = "rec",
    ):
        """
        绘制识别结果并保存/显示

        Args:
            image: 原始图像 (OpenCV 格式)
            roi: 感兴趣区域 (x, y, w, h) - 原始分辨率坐标
            cards: 识别到的卡牌列表
            filename_prefix: 保存文件名前缀
        """
        settings = get_settings()
        if not settings.debug:
            return

        try:
            debug_img = image.copy()

            # 1. 画 ROI (红色框)
            if roi:
                rx, ry, rw, rh = roi
                cv2.rectangle(
                    debug_img,
                    (rx, ry),
                    (rx + rw, ry + rh),
                    (0, 0, 255),  # Red
                    3,
                )
                cv2.putText(
                    debug_img,
                    "ROI",
                    (rx, ry - 10),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    1.0,
                    (0, 0, 255),
                    2,
                )

            # 2. 画识别结果 (蓝色框)
            for card in cards:
                x1, y1, x2, y2 = card.box
                cv2.rectangle(debug_img, (x1, y1), (x2, y2), (255, 0, 0), 2)

                short_name = card.name.split("/")[-1]
                label = f"{short_name} ({card.confidence:.2f})"

                text_y = max(y1 - 10, 30)
                cv2.putText(
                    debug_img,
                    label,
                    (x1, text_y),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.6,
                    (255, 0, 0),
                    2,
                )

            # 3. 保存或显示
            # 使用系统临时目录 /tmp，避免污染项目目录
            # 兼容性: 重新导入 Path 以防万一 (虽然上面已导入)
            from pathlib import Path

            debug_dir = Path("/tmp") / "ptcgp_auto_debug"
            debug_dir.mkdir(parents=True, exist_ok=True)

            # 使用固定文件名，方便查看和覆盖
            filepath = debug_dir / f"{filename_prefix}.png"

            cv2.imwrite(str(filepath), debug_img)
            # 显式打印路径，方便 CLI 用户
            print(f"Debug image saved to: {filepath}")
            logger.debug(f"调试图片已保存: {filepath}")

            # 如果是 Kitty 终端，直接显示
            if DebugVisualizer.is_kitty():
                print(f"\n[Debug Image: {filepath.name}]", flush=True)

                # 缩放图片用于终端显示 (避免太大刷屏)
                # 0.5x 缩放 -> 1080p 变为 ~540px 宽，适合大多数终端查看
                h, w = debug_img.shape[:2]
                display_scale = 0.5
                new_w, new_h = int(w * display_scale), int(h * display_scale)

                # 确保尺寸至少为 1x1
                new_w = max(1, new_w)
                new_h = max(1, new_h)

                display_img_cv = cv2.resize(
                    debug_img, (new_w, new_h), interpolation=cv2.INTER_AREA
                )

                # 转换为 PIL Image
                display_img_pil = Image.fromarray(
                    cv2.cvtColor(display_img_cv, cv2.COLOR_BGR2RGB)
                )

                DebugVisualizer.show_in_kitty(display_img_pil)
                print(flush=True)  # 换行并刷新

        except Exception as e:
            logger.warning(f"生成调试图失败: {e}")
