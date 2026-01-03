"""基础动作模块"""

import time
from typing import Dict

import config
from .utils import find_text_by_variants


class BaseActions:
    """基础动作处理"""

    def __init__(self, adb, recognizer):
        self.adb = adb
        self.recognizer = recognizer

    def click_identifier(self, screenshot, match_info: Dict):
        """点击识别到的文字位置"""
        box = match_info.get("box")
        if box:
            print(f"  -> 点击: {match_info.get('identifier', 'unknown')}")
            self.adb.tap_center(box)

    def click_continue(self, screenshot, match_info: Dict):
        """点击屏幕中央继续"""
        print("  -> 点击屏幕继续")
        self.adb.tap(config.SCREEN_WIDTH // 2, config.SCREEN_HEIGHT // 2)

    def click_cancel(self, screenshot, match_info: Dict):
        """点击取消按钮"""
        ocr_results = match_info.get("ocr_results", [])
        cancel_item = find_text_by_variants(ocr_results, "cancel")
        if cancel_item:
            print("  -> 点击取消")
            self.adb.tap_center(cancel_item['box'])
            return
        # 如果没找到取消，尝试点击屏幕继续
        print("  -> 未找到取消按钮，点击屏幕继续")
        self.adb.tap(config.SCREEN_WIDTH // 2, config.SCREEN_HEIGHT // 2)

    def click_template(self, screenshot, match_info: Dict):
        """点击模板位置"""
        box = match_info.get("box")
        if box:
            print(f"  -> 点击模板: {match_info.get('template', 'unknown')}")
            self.adb.tap_center(box)

    def wait(self, screenshot, match_info: Dict):
        """等待（对战中）"""
        print("  -> 对战中，等待...")
        time.sleep(config.WAIT_BATTLE_CHECK_INTERVAL)
