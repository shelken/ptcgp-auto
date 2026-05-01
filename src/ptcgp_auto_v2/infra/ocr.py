# -*- coding: utf-8 -*-
"""
OCR 识别模块

使用 Apple Vision Framework 进行文字识别。
"""

import io
import logging
from dataclasses import dataclass
from typing import List, Optional

from PIL import Image

from ptcgp_auto_v2.config.constants import DEFAULT_OCR_LEVEL
from ptcgp_auto_v2.config.lang import DEFAULT_OCR_LANGUAGES
from ptcgp_auto_v2.utils.dependency_guard import run_failfast_call

logger = logging.getLogger(__name__)

OCR_CALL_TIMEOUT_SECONDS = 20.0
# Apple 文档写默认 1/32；PyObjC 实测初始值是 0.0。显式设置可减少小噪点干扰，稳定按钮文字分割。
OCR_MIN_TEXT_HEIGHT_RATIO = 1.0 / 32.0
OCR_VISION_REVISION = 3


@dataclass
class OcrResult:
    """OCR 识别结果"""

    text: str
    box: tuple[int, int, int, int]  # (x1, y1, x2, y2)
    confidence: float

    def to_dict(self) -> dict:
        """转换为字典格式（兼容 v1）"""
        return {
            "text": self.text,
            "box": self.box,
            "confidence": self.confidence,
        }


class OcrEngine:
    """
    OCR 识别引擎

    封装 Apple Vision Framework 的 OCR 功能。
    仅支持 macOS 平台。
    """

    def __init__(
        self,
        recognition_level: str = DEFAULT_OCR_LEVEL,
        languages: Optional[List[str]] = None,
        minimum_text_height_ratio: float = OCR_MIN_TEXT_HEIGHT_RATIO,
        automatically_detects_language: bool = False,
        uses_language_correction: bool = False,
        revision: int = OCR_VISION_REVISION,
    ):
        """
        初始化 OCR 引擎

        Args:
            recognition_level: 识别级别，"fast" 或 "accurate"
            languages: 识别语言列表，如 ["zh-Hant", "en-US"]
        """
        self.recognition_level = recognition_level
        self.languages = languages or DEFAULT_OCR_LANGUAGES
        self.minimum_text_height_ratio = minimum_text_height_ratio
        self.automatically_detects_language = automatically_detects_language
        self.uses_language_correction = uses_language_correction
        self.revision = revision

        # 验证平台
        self._validate_platform()

    def _validate_platform(self):
        """验证是否在 macOS 平台上运行"""
        import platform

        if platform.system() != "Darwin":
            raise RuntimeError("OCR 引擎仅支持 macOS 平台")

    def recognize(self, image: Image.Image) -> List[OcrResult]:
        """
        识别图片中的文字

        Args:
            image: PIL Image 对象

        Returns:
            OcrResult 列表
        """
        if image is None:
            logger.error("OCR 输入图片为 None")
            raise RuntimeError("OCR 输入图片为 None")

        width = image.width
        height = image.height

        if width <= 0 or height <= 0:
            logger.warning(f"OCR 忽略无效图片尺寸: {width}x{height}")
            raise RuntimeError(f"OCR 图片尺寸无效: {width}x{height}")

        # 转换图片为 PNG 数据
        try:
            buffer = io.BytesIO()
            image.save(buffer, format="PNG")
            png_data = buffer.getvalue()
            buffer.close()
        except (ValueError, TypeError) as e:
            logger.exception("OCR 图片转换 PNG 失败")
            raise RuntimeError("OCR 图片转换 PNG 失败") from e

        if not png_data:
            logger.warning("OCR 图片转换后数据为空")
            raise RuntimeError("OCR 图片转换后数据为空")

        return run_failfast_call(
            logger,
            "ocr.recognize",
            OCR_CALL_TIMEOUT_SECONDS,
            lambda: self._recognize_png(png_data, width, height),
        )

    def _recognize_png(
        self,
        png_data: bytes,
        width: int,
        height: int,
    ) -> List[OcrResult]:
        import objc
        import Quartz
        import Vision
        from Foundation import NSData

        try:
            create_image_source = Quartz.CGImageSourceCreateWithData
            create_cg_image = Quartz.CGImageSourceCreateImageAtIndex
        except (AttributeError, KeyError) as e:
            logger.exception("OCR 缺少 Quartz 图片解码接口")
            raise RuntimeError("OCR 缺少 Quartz 图片解码接口") from e

        results: List[OcrResult] = []
        with objc.autorelease_pool():
            ns_data = NSData.dataWithBytes_length_(png_data, len(png_data))
            if ns_data is None:
                raise RuntimeError("无法创建 NSData")

            image_source = create_image_source(ns_data, None)
            if image_source is None:
                raise RuntimeError("无法创建 CGImageSource")

            cg_image = create_cg_image(image_source, 0, None)
            if cg_image is None:
                raise RuntimeError("无法创建 CGImage")

            request = Vision.VNRecognizeTextRequest.alloc().init()
            request.setRevision_(self.revision)
            if self.recognition_level == "fast":
                request.setRecognitionLevel_(Vision.VNRequestTextRecognitionLevelFast)
            else:
                request.setRecognitionLevel_(
                    Vision.VNRequestTextRecognitionLevelAccurate
                )

            request.setRecognitionLanguages_(self.languages)
            request.setAutomaticallyDetectsLanguage_(self.automatically_detects_language)
            request.setUsesLanguageCorrection_(self.uses_language_correction)
            request.setMinimumTextHeight_(self.minimum_text_height_ratio)

            handler = Vision.VNImageRequestHandler.alloc().initWithCGImage_options_(
                cg_image, None
            )
            success = handler.performRequests_error_([request], None)
            if isinstance(success, tuple):
                success = success[0]
            if not success:
                raise RuntimeError("OCR 请求执行失败")

            observations = request.results()
            if not observations:
                return results

            for observation in observations:
                top_candidate = observation.topCandidates_(1)
                if not top_candidate or len(top_candidate) == 0:
                    continue
                text = str(top_candidate[0].string())
                confidence = float(top_candidate[0].confidence())
                bounding_box = observation.boundingBox()
                x = bounding_box.origin.x
                y = bounding_box.origin.y
                w = bounding_box.size.width
                h = bounding_box.size.height

                x1 = int(x * width)
                y1 = int((1 - y - h) * height)
                x2 = int((x + w) * width)
                y2 = int((1 - y) * height)

                results.append(
                    OcrResult(
                        text=text,
                        box=(x1, y1, x2, y2),
                        confidence=confidence,
                    )
                )

        return results

    def recognize_as_dict(self, image: Image.Image) -> List[dict]:
        """
        识别图片中的文字，返回字典格式（兼容 v1）

        Args:
            image: PIL Image 对象

        Returns:
            字典列表，每项包含 text, box, confidence
        """
        results = self.recognize(image)
        return [r.to_dict() for r in results]

    def _normalize_text(self, text: str) -> tuple[str, str]:
        text_lower = text.strip().lower()
        text_normalized = "".join(text_lower.split())
        return text_lower, text_normalized

    def _matches(
        self, target_lower: str, target_normalized: str, text: str, exact_match: bool
    ) -> bool:
        text_lower, text_normalized = self._normalize_text(text)
        if exact_match:
            return target_lower == text_lower
        return (
            target_lower == text_lower
            or target_lower in text_lower
            or target_normalized in text_normalized
        )

    def match_text(self, target: str, text: str, exact_match: bool = False) -> bool:
        """判断文本是否匹配（公共接口）"""
        target_lower, target_normalized = self._normalize_text(target)
        return self._matches(target_lower, target_normalized, text, exact_match)

    def find_text(
        self,
        image: Image.Image,
        target: str,
        exact_match: bool = False,
    ) -> Optional[OcrResult]:
        """
        在图片中查找指定文字

        Args:
            image: PIL Image 对象
            target: 要查找的文字
            exact_match: 是否精确匹配

        Returns:
            找到的 OcrResult，未找到返回 None
        """
        results = self.recognize(image)
        target_lower, target_normalized = self._normalize_text(target)

        for result in results:
            if self._matches(target_lower, target_normalized, result.text, exact_match):
                return result

        return None
