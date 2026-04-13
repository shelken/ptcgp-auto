"""
文本识别相关能力
"""

from typing import Optional, Tuple, List, Dict

from PIL import Image

from ptcgp_auto import config
from ptcgp_auto.logger import get_logger
from ptcgp_auto.recognizer_parts.ocr import perform_ocr

logger = get_logger(__name__)


class TextRecognizerMixin:
    """文本识别能力"""

    def ocr_full_screen(self, screenshot: Image.Image) -> List[Dict]:
        """对整个屏幕进行 OCR"""
        results = perform_ocr(screenshot)

        ocr_str = ", ".join(
            [
                f'"{item["text"]}"@({item["box"][0]},{item["box"][1]})'
                for item in results
            ]
        )
        logger.debug(f"OCR({len(results)}): {ocr_str}")

        return results

    def find_text(
        self,
        screenshot: Image.Image,
        target_text: str,
        partial: bool = True,
    ) -> Optional[Tuple[int, int, int, int]]:
        """在截图中查找包含指定文字的区域"""
        ocr_results = self.ocr_full_screen(screenshot)

        for item in ocr_results:
            text = item["text"]
            if partial:
                if target_text.lower() in text.lower():
                    logger.debug(f"找到文字 '{target_text}' 在 '{text}'")
                    return item["box"]
            else:
                if target_text.lower() == text.lower():
                    logger.debug(f"找到文字 '{target_text}'")
                    return item["box"]

        logger.debug(f"未找到文字: {target_text}")
        return None

    def find_text_variants(
        self,
        screenshot: Image.Image,
        pattern_key: str,
        partial: bool = False,
    ) -> Optional[Tuple[int, int, int, int]]:
        """在截图中查找多语言文本模式"""
        if pattern_key not in config.TEXT_PATTERNS:
            logger.warning(f"未知的文本模式键: {pattern_key}")
            return None

        patterns = config.TEXT_PATTERNS[pattern_key]
        ocr_results = self.ocr_full_screen(screenshot)

        for item in ocr_results:
            text = item["text"].strip()
            for pattern in patterns:
                if pattern.lower().strip() == text.lower():
                    logger.debug(f"找到文字模式(精确) '{pattern}' = '{text}'")
                    return item["box"]

        if partial:
            for item in ocr_results:
                text = item["text"].strip()
                for pattern in patterns:
                    if pattern.lower().strip() in text.lower():
                        logger.debug(f"找到文字模式(部分) '{pattern}' 在 '{text}'")
                        return item["box"]

        logger.debug(f"未找到任何 '{pattern_key}' 模式")
        return None
