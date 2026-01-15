"""主页相关动作模块"""

import re
from typing import Dict

from logger import get_logger
from .utils import find_text_by_variants

logger = get_logger(__name__)


class HomeActions:
    """主页相关动作处理"""

    def __init__(self, adb, recognizer=None, state=None):
        self.adb = adb
        self.recognizer = recognizer
        self.state = state

    def handle_game_home(self, screenshot, match_info: Dict):
        """处理游戏主页 - 检查用户信息后决定下一步"""
        # 如果没有用户信息，先去获取
        if self.state and not self.state.has_user_info():
            # 点击社群图标
            if self.recognizer:
                community_box = self.recognizer.find_template(
                    screenshot, "icon_community", threshold=0.7
                )
                if community_box:
                    logger.info("  -> 需要获取用户信息，点击社群图标")
                    self.adb.tap_center(community_box)
                    return

        # 已有用户信息，点击对战图标
        if self.recognizer:
            battle_box = self.recognizer.find_template(
                screenshot, "icon_battle", threshold=0.7
            )
            if battle_box:
                logger.info("  -> 点击对战图标")
                self.adb.tap_center(battle_box)
                return

        logger.error("  -> 未找到目标图标")

    def find_incomplete(self, screenshot, match_info: Dict):
        """在单人对战主页寻找未完成任务"""
        ocr_results = match_info.get("ocr_results", [])

        # 查找分级对战入口
        ranked_item = find_text_by_variants(ocr_results, "ranked_battle")
        if ranked_item:
            logger.info("  -> 进入分级对战")
            self.adb.tap_center(ranked_item['box'])
            return

        # 查找有进度数字的任务
        for item in ocr_results:
            text = item['text'].strip()
            if re.search(r'\d+\s*/\s*\d+', text):
                logger.info(f"  -> 找到未完成任务: {text}")
                self.adb.tap_center(item['box'])
                return

        logger.info("  -> 未找到可操作的任务")

    def click_solo_battle(self, screenshot, match_info: Dict):
        """在主菜单点击单人对战"""
        ocr_results = match_info.get("ocr_results", [])

        solo_item = find_text_by_variants(ocr_results, "solo_battle")
        if solo_item:
            logger.info("  -> 点击单人对战")
            self.adb.tap_center(solo_item['box'])
            return

        logger.error("  -> 未找到单人对战入口")
