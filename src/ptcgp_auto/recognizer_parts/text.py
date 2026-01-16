"""
文本识别相关能力
"""

from typing import Optional, Tuple, List, Dict
import re

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

    def wait_for_text_variants(
        self,
        adb_controller,
        pattern_key: str,
        timeout: int = None,
        check_interval: int = None,
    ) -> bool:
        """等待多语言文本模式出现"""
        import time

        timeout = timeout or config.WAIT_BATTLE_TIMEOUT
        check_interval = check_interval or config.WAIT_BATTLE_CHECK_INTERVAL

        start_time = time.time()

        while time.time() - start_time < timeout:
            screenshot = adb_controller.screenshot()
            if screenshot and self.find_text_variants(screenshot, pattern_key):
                return True

            time.sleep(check_interval)

        logger.debug(f"等待 '{pattern_key}' 模式超时")
        return False

    def check_complete_status(self, screenshot: Image.Image) -> Dict[str, bool]:
        """检查界面上的完成状态"""
        ocr_results = self.ocr_full_screen(screenshot)

        result = {"complete": False, "clear": False, "progress": None}

        for item in ocr_results:
            text = item["text"].upper()

            if "COMPLETE" in text:
                result["complete"] = True

            if "CLEAR" in text:
                result["clear"] = True

            progress_match = re.search(r"(\d+)\s*/\s*(\d+)", item["text"])
            if progress_match:
                result["progress"] = item["text"]

        return result

    def wait_for_text(
        self,
        adb_controller,
        target_text: str,
        timeout: int = None,
        check_interval: int = None,
    ) -> bool:
        """等待指定文字出现"""
        import time

        timeout = timeout or config.WAIT_BATTLE_TIMEOUT
        check_interval = check_interval or config.WAIT_BATTLE_CHECK_INTERVAL

        start_time = time.time()

        while time.time() - start_time < timeout:
            screenshot = adb_controller.screenshot()
            if screenshot and self.find_text(screenshot, target_text):
                return True

            time.sleep(check_interval)

        logger.info(f"等待 '{target_text}' 超时")
        return False
