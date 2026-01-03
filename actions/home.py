"""主页相关动作模块"""

import re
from typing import Dict

from .utils import find_text_by_variants


class HomeActions:
    """主页相关动作处理"""

    def __init__(self, adb):
        self.adb = adb

    def find_incomplete(self, screenshot, match_info: Dict):
        """在单人对战主页寻找未完成任务"""
        ocr_results = match_info.get("ocr_results", [])

        # 查找分级对战入口
        ranked_item = find_text_by_variants(ocr_results, "ranked_battle")
        if ranked_item:
            print("  -> 进入分级对战")
            self.adb.tap_center(ranked_item['box'])
            return

        # 查找有进度数字的任务
        for item in ocr_results:
            text = item['text'].strip()
            if re.search(r'\d+\s*/\s*\d+', text):
                print(f"  -> 找到未完成任务: {text}")
                self.adb.tap_center(item['box'])
                return

        print("  -> 未找到可操作的任务")

    def click_solo_battle(self, screenshot, match_info: Dict):
        """在主菜单点击单人对战"""
        ocr_results = match_info.get("ocr_results", [])

        solo_item = find_text_by_variants(ocr_results, "solo_battle")
        if solo_item:
            print("  -> 点击单人对战")
            self.adb.tap_center(solo_item['box'])
            return

        print("  -> 未找到单人对战入口")
