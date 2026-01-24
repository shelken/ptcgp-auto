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

from ptcgp_auto_v2.config.constants import DEFAULT_OCR_LANGUAGES, DEFAULT_OCR_LEVEL

logger = logging.getLogger(__name__)


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
    ):
        """
        初始化 OCR 引擎

        Args:
            recognition_level: 识别级别，"fast" 或 "accurate"
            languages: 识别语言列表，如 ["zh-Hant", "en-US"]
        """
        self.recognition_level = recognition_level
        self.languages = languages or DEFAULT_OCR_LANGUAGES

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
        # 延迟导入 macOS 框架
        import Vision
        import Quartz
        from Foundation import NSData
        import objc

        width = image.width
        height = image.height

        # 转换图片为 PNG 数据
        buffer = io.BytesIO()
        image.save(buffer, format="PNG")
        png_data = buffer.getvalue()
        buffer.close()

        results = []

        with objc.autorelease_pool():
            # 创建 CGImage
            ns_data = NSData.dataWithBytes_length_(png_data, len(png_data))
            image_source = Quartz.CGImageSourceCreateWithData(ns_data, None)
            cg_image = Quartz.CGImageSourceCreateImageAtIndex(image_source, 0, None)

            if cg_image is None:
                logger.error("无法创建 CGImage")
                return []

            # 创建识别请求
            request = Vision.VNRecognizeTextRequest.alloc().init()

            # 设置识别级别
            if self.recognition_level == "fast":
                request.setRecognitionLevel_(Vision.VNRequestTextRecognitionLevelFast)
            else:
                request.setRecognitionLevel_(Vision.VNRequestTextRecognitionLevelAccurate)

            # 设置识别语言
            request.setRecognitionLanguages_(self.languages)
            request.setAutomaticallyDetectsLanguage_(True)

            # 执行识别
            handler = Vision.VNImageRequestHandler.alloc().initWithCGImage_options_(
                cg_image, None
            )

            success = handler.performRequests_error_([request], None)

            if not success:
                logger.error("OCR 请求执行失败")
                return []

            # 处理结果
            observations = request.results()

            if observations:
                for observation in observations:
                    top_candidate = observation.topCandidates_(1)
                    if top_candidate and len(top_candidate) > 0:
                        text = str(top_candidate[0].string())
                        confidence = float(top_candidate[0].confidence())

                        # 转换坐标（Vision 坐标系原点在左下角）
                        bounding_box = observation.boundingBox()
                        x = bounding_box.origin.x
                        y = bounding_box.origin.y
                        w = bounding_box.size.width
                        h = bounding_box.size.height

                        x1 = int(x * width)
                        y1 = int((1 - y - h) * height)
                        x2 = int((x + w) * width)
                        y2 = int((1 - y) * height)

                        results.append(OcrResult(
                            text=text,
                            box=(x1, y1, x2, y2),
                            confidence=confidence,
                        ))

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

    def _matches(self, target_lower: str, target_normalized: str, text: str, exact_match: bool) -> bool:
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

    def find_all_text(
        self,
        image: Image.Image,
        target: str,
        exact_match: bool = False,
    ) -> List[OcrResult]:
        """
        在图片中查找所有匹配的文字

        Args:
            image: PIL Image 对象
            target: 要查找的文字
            exact_match: 是否精确匹配

        Returns:
            匹配的 OcrResult 列表
        """
        results = self.recognize(image)
        target_lower, target_normalized = self._normalize_text(target)
        matches = []

        for result in results:
            if self._matches(target_lower, target_normalized, result.text, exact_match):
                matches.append(result)

        return matches
