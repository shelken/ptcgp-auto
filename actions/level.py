"""等级选择动作模块"""

import re
import sys
import time
from typing import Dict, List, Callable

import config
from .utils import ScrollHelper, go_back


class LevelActions:
    """等级选择相关动作处理"""

    def __init__(self, adb, recognizer, state, should_switch_checker: Callable[[], bool]):
        self.adb = adb
        self.recognizer = recognizer
        self.state = state
        self._should_switch_to_higher_priority_level = should_switch_checker
        self._scroll_helper = ScrollHelper(adb, recognizer, max_attempts=10, ratio=0.21)

    def select_level(self, screenshot, match_info: Dict, needs_state_init: bool, on_init_complete: Callable, reset_pack_state: Callable):
        """选择未完成的等级

        Args:
            screenshot: 当前截图
            match_info: 匹配信息，包含 OCR 结果
            needs_state_init: 是否需要初始化状态
            on_init_complete: 初始化完成回调
            reset_pack_state: 重置卡包检查状态的回调
        """
        ocr_results = match_info.get("ocr_results", [])

        # 重置卡包检查标志（进入等级选择页面时）
        reset_pack_state()

        # 如果需要初始化，先同步所有等级状态
        if needs_state_init:
            self._sync_level_complete_status(ocr_results, screenshot)
            on_init_complete()

        # 检查是否应该切换到更高优先级的等级
        if self._should_switch_to_higher_priority_level():
            print("  -> 返回上级页面以选择更高优先级等级")
            self.state.set_current_level(None)
            go_back(self.adb, self.recognizer, screenshot)
            return

        # 按优先级逐个查找等级
        for level in config.BATTLE_LEVELS:
            if self.state.is_level_complete(level):
                continue

            found = self._find_and_click_level(level, ocr_results, screenshot)
            if found:
                return

        # 所有等级都已完成
        print("  -> 所有等级都已完成！")
        print("=" * 50)
        print("恭喜！所有分级对战任务已完成！")
        print("=" * 50)
        sys.exit(0)

    def _find_and_click_level(self, level: str, ocr_results: List[Dict], screenshot) -> bool:
        """查找并点击指定等级

        Returns:
            True 如果找到并点击了，False 如果没找到
        """
        max_attempts = 10
        last_texts = set()

        for attempt in range(max_attempts):
            if attempt > 0:
                print(f"  -> 滑动查找 {level} (第{attempt}次)")
                self.adb.swipe_up(ratio=0.21)  # 约 400/1920
                time.sleep(0.8)
                screenshot = self.adb.screenshot()
                if screenshot:
                    ocr_results = self.recognizer.ocr_full_screen(screenshot)
                else:
                    continue

            current_texts = set(item['text'].strip() for item in ocr_results)

            # 在当前 OCR 结果中查找该等级
            for item in ocr_results:
                text = item['text'].strip()
                if level in text:
                    level_y = (item['box'][1] + item['box'][3]) // 2

                    for other_item in ocr_results:
                        other_y = (other_item['box'][1] + other_item['box'][3]) // 2
                        if abs(other_y - level_y) < 150:
                            other_text = other_item['text'].strip()

                            if 'COMPLETE' in other_text.upper():
                                self.state.set_level_complete(level, True)
                                return False

                            if re.search(r'\d+\s*/\s*\d+', other_text):
                                print(f"  -> 选择等级: {level} ({other_text})")
                                self.state.set_current_level(level)
                                self.adb.tap_center(item['box'])
                                return True

            if attempt > 0 and current_texts == last_texts:
                print(f"  -> 已滑动到底部，未找到 {level}")
                break

            last_texts = current_texts

        return False

    def _sync_level_complete_status(self, ocr_results: List[Dict], screenshot):
        """同步所有等级的完成状态"""
        print("  [初始化] 正在同步等级完成状态...")

        synced_levels = set()
        max_attempts = 10
        last_texts = set()

        for attempt in range(max_attempts):
            if attempt > 0:
                self.adb.swipe_up(ratio=0.21)  # 约 400/1920
                time.sleep(0.8)
                screenshot = self.adb.screenshot()
                if screenshot:
                    ocr_results = self.recognizer.ocr_full_screen(screenshot)

            current_texts = set(item['text'].strip() for item in ocr_results)

            for item in ocr_results:
                text = item['text'].strip()
                for level in config.BATTLE_LEVELS:
                    if level in text and level not in synced_levels:
                        level_y = (item['box'][1] + item['box'][3]) // 2
                        is_complete = False
                        for other in ocr_results:
                            other_y = (other['box'][1] + other['box'][3]) // 2
                            if abs(other_y - level_y) < 150:
                                if 'COMPLETE' in other['text'].upper():
                                    is_complete = True
                                    break
                        if is_complete:
                            self.state.set_level_complete(level, True)
                            print(f"  [初始化] {level} = COMPLETE")
                        else:
                            print(f"  [初始化] {level} = 进行中")
                        synced_levels.add(level)

            if attempt > 0 and current_texts == last_texts:
                print("  [初始化] 已滑动到底部")
                break

            last_texts = current_texts

        self.adb.swipe_down(ratio=0.42)  # 约 800/1920
        time.sleep(0.5)

        print(f"  [初始化] 同步完成，共 {len(synced_levels)} 个等级")
