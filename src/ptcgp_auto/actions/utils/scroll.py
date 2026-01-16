"""滚动查找工具"""

import time
from typing import Callable, TypeVar, Optional, Set, List, Dict

T = TypeVar('T')


class ScrollHelper:
    """滚动查找辅助类"""

    def __init__(self, adb, recognizer, max_attempts: int = 10, ratio: float = 0.21, delay: float = 0.8):
        """
        Args:
            adb: AdbController 实例
            recognizer: Recognizer 实例
            max_attempts: 最大滑动次数
            ratio: 滑动距离占屏幕高度的比例（默认 0.21 约等于 1920 下的 400px）
            delay: 滑动后等待时间
        """
        self.adb = adb
        self.recognizer = recognizer
        self.max_attempts = max_attempts
        self.ratio = ratio
        self.delay = delay

    def scroll_and_find(
        self,
        finder: Callable[[any, List[Dict]], Optional[T]],
        screenshot,
        ocr_results: List[Dict],
        on_scroll: Callable[[int], None] = None
    ) -> Optional[T]:
        """滑动查找，直到找到目标或到底

        Args:
            finder: 查找函数，接收 (screenshot, ocr_results)，返回找到的结果或 None
            screenshot: 初始截图
            ocr_results: 初始 OCR 结果
            on_scroll: 滑动时的回调，接收滑动次数

        Returns:
            找到的结果，或 None
        """
        last_texts: Set[str] = set()

        for attempt in range(self.max_attempts):
            if attempt > 0:
                if on_scroll:
                    on_scroll(attempt)
                self.adb.swipe_up(ratio=self.ratio)
                time.sleep(self.delay)
                screenshot = self.adb.screenshot()
                if screenshot:
                    ocr_results = self.recognizer.ocr_full_screen(screenshot)
                else:
                    continue

            # 尝试查找
            result = finder(screenshot, ocr_results)
            if result is not None:
                return result

            # 检测是否到底
            current_texts = {item['text'].strip() for item in ocr_results}
            if attempt > 0 and current_texts == last_texts:
                break
            last_texts = current_texts

        return None

    def is_at_bottom(self, current_texts: Set[str], last_texts: Set[str]) -> bool:
        """检测是否已滑动到底部"""
        return bool(last_texts) and current_texts == last_texts
