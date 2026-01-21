"""基础动作模块"""

import time
from typing import Dict

from ptcgp_auto import config
from ptcgp_auto.logger import get_logger

logger = get_logger(__name__)
from .utils import find_text_by_variants, find_auto_mode_button


class BaseActions:
    """基础动作处理"""

    def __init__(self, adb, recognizer):
        self.adb = adb
        self.recognizer = recognizer

    def click_identifier(self, screenshot, match_info: Dict):
        """点击识别到的文字位置"""
        box = match_info.get("box")
        if box:
            logger.info(f"  -> 点击: {match_info.get('identifier', 'unknown')}")
            self.adb.tap_center(box)

    def tap_screen_center(self, screenshot, match_info: Dict):
        """点击屏幕中心"""
        logger.info("  -> 点击屏幕中心")
        self.adb.tap(config.SCREEN_WIDTH // 2, config.SCREEN_HEIGHT // 2)

    def click_continue_button(self, screenshot, match_info: Dict):
        """查找并点击继续按钮"""
        ocr_results = match_info.get("ocr_results", [])
        item = find_text_by_variants(ocr_results, "continue")
        if item:
            logger.info(f"  -> 点击继续按钮: {item['text']}")
            self.adb.tap_center(item["box"])
        else:
            logger.info("  -> 未找到继续按钮，点击屏幕中心")
            self.adb.tap(config.SCREEN_WIDTH // 2, config.SCREEN_HEIGHT // 2)

    def click_cancel(self, screenshot, match_info: Dict):
        """点击取消按钮"""
        ocr_results = match_info.get("ocr_results", [])
        cancel_item = find_text_by_variants(ocr_results, "cancel")
        if cancel_item:
            logger.info("  -> 点击取消")
            self.adb.tap_center(cancel_item["box"])
            return
        # 如果没找到取消，尝试点击屏幕继续
        logger.info("  -> 未找到取消按钮，点击屏幕继续")
        self.adb.tap(config.SCREEN_WIDTH // 2, config.SCREEN_HEIGHT // 2)

    def click_template(self, screenshot, match_info: Dict):
        """点击模板位置

        支持两种场景：
        1. 页面通过模板匹配识别 - 直接点击匹配到的模板位置
        2. 页面通过文字匹配识别 - 查找 action_template 指定的模板并点击
        """
        box = match_info.get("box")
        template_name = match_info.get("template")

        # 如果没有模板 box（页面通过文字匹配），则查找 action_template
        if not template_name:
            page_info = match_info.get("page_info", {})
            template_name = page_info.get("action_template")
            if template_name:
                box = self.recognizer.find_template(screenshot, template_name)

        if box:
            logger.info(f"  -> 点击模板: {template_name or 'unknown'}")
            self.adb.tap_center(box)
        else:
            logger.error(f"  -> 未找到模板: {template_name}")

    def wait(self, screenshot, match_info: Dict):
        """等待（对战中）"""
        logger.info("  -> 对战中，等待...")
        time.sleep(config.WAIT_BATTLE_CHECK_INTERVAL)

    def click_auto_mode(self, screenshot, match_info: Dict):
        """点击自动模式按钮"""
        ocr_results = match_info.get("ocr_results", [])
        result = find_auto_mode_button(ocr_results)
        if result:
            auto_item, _ = result
            logger.info(f"  -> 点击自动模式: {auto_item['text']}")
            self.adb.tap_center(auto_item["box"])
            return
        # 没找到自动按钮，点击屏幕继续
        logger.info("  -> 未找到自动按钮，点击屏幕继续")
        self.adb.tap(config.SCREEN_WIDTH // 2, config.SCREEN_HEIGHT // 2)
