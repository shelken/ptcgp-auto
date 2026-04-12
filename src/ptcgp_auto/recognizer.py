"""
识别器 - OCR + 模板匹配 (使用 Apple Vision Framework)
"""

from pathlib import Path
from typing import Optional, Dict

import numpy as np

from ptcgp_auto.logger import get_logger
from ptcgp_auto.recognizer_parts.color import ColorDetectorMixin
from ptcgp_auto.recognizer_parts.constants import COLORS as COLORS, COLOR_STATES as COLOR_STATES
from ptcgp_auto.recognizer_parts.ocr import perform_ocr as perform_ocr
from ptcgp_auto.recognizer_parts.template_matcher import TemplateMatcherMixin
from ptcgp_auto.recognizer_parts.text import TextRecognizerMixin

logger = get_logger(__name__)


class Recognizer(TemplateMatcherMixin, TextRecognizerMixin, ColorDetectorMixin):
    """界面识别器"""

    def __init__(self, templates_dir: str = "templates"):
        self.templates_dir = Path(templates_dir)
        self.templates: Dict[str, np.ndarray] = {}
        logger.info("使用 Apple Vision Framework 进行 OCR（原生 Apple Silicon 加速）")


_recognizer: Optional[Recognizer] = None


def get_recognizer() -> Recognizer:
    """获取全局识别器实例"""
    global _recognizer
    if _recognizer is None:
        _recognizer = Recognizer()
    return _recognizer

