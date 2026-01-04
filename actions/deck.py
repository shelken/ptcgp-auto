"""牌组列表动作模块"""

import re
import time
from typing import Dict, List, Optional, Callable

import config
from .utils import go_back, find_text_by_variants, close_popup, detect_and_close_popup


class DeckActions:
    """牌组列表相关动作处理"""

    def __init__(self, adb, recognizer, state, should_switch_checker: Callable[[], bool]):
        self.adb = adb
        self.recognizer = recognizer
        self.state = state
        self._should_switch_to_higher_priority_level = should_switch_checker

    def handle_deck_list(
        self,
        screenshot,
        match_info: Dict,
        needs_state_init: bool,
        all_packs_checked: bool,
        current_pack_id: Optional[str],     # 组合 ID
        current_pack_name: Optional[str],   # 卡包名称（用于显示）
        set_all_packs_checked: Callable[[bool], None],
        set_current_pack_name: Callable[[str], None]
    ):
        """处理牌组列表页面"""
        ocr_results = match_info.get("ocr_results", [])
        current_level = self.state.get_current_level()

        # 如果所有卡包都已检查完毕，返回上级页面
        if all_packs_checked:
            print("  -> 所有卡包都已检查，返回上级页面")
            set_all_packs_checked(False)
            go_back(self.adb, self.recognizer, screenshot)
            return

        # 如果需要初始化状态且当前等级未设置，返回上级页面
        if needs_state_init and not current_level:
            print("  -> 需要初始化状态，返回上级页面")
            go_back(self.adb, self.recognizer, screenshot)
            return

        # 尝试从页面识别当前等级
        detected_level = self._detect_level_from_ocr(ocr_results)
        if detected_level:
            if current_level and detected_level != current_level:
                print(f"  [等级] 检测到等级不一致: state={current_level}, 实际={detected_level}")
                print(f"  -> 更新 current_level 为 {detected_level}")
            current_level = detected_level
            self.state.set_current_level(current_level)

        # 如果 current_level 仍未设置，返回上级重新选择
        if not current_level:
            print("  -> 无法识别当前等级，返回上级重新选择")
            go_back(self.adb, self.recognizer, screenshot)
            return

        # 检查是否应该切换到更高优先级的等级
        if self._should_switch_to_higher_priority_level():
            print("  -> 返回上级页面以选择更高优先级等级")
            go_back(self.adb, self.recognizer, screenshot)
            return

        # 检查是否没有可用对战
        no_battles_variants = config.TEXT_VARIANTS.get("no_battles_available", [])
        for item in ocr_results:
            text = item['text'].strip().lower()
            for variant in no_battles_variants:
                if variant.lower() in text:
                    print("  -> 当前难度没有可用对战，标记卡包完成并返回")
                    if current_level and current_pack_id:
                        self.state.set_pack_complete(current_level, current_pack_id, True)
                    # 点击扩充组查看更多卡包
                    expansion_item = find_text_by_variants(ocr_results, "expansion_button")
                    if expansion_item:
                        self.adb.tap_center(expansion_item['box'])
                        return
                    go_back(self.adb, self.recognizer, screenshot)
                    return

        # 尝试识别当前卡包名称
        pack_name = self._extract_pack_name(ocr_results)
        if pack_name:
            set_current_pack_name(pack_name)
            print(f"  [卡包] {pack_name}")

        # 检查当前卡包是否已标记为完成
        if current_level and current_pack_id:
            if self.state.is_pack_complete(current_level, current_pack_id):
                print(f"  -> {current_pack_name or current_pack_id} 在 {current_level} 已完成，进入扩充组选择其他卡包")
                expansion_item = find_text_by_variants(ocr_results, "expansion_button")
                if expansion_item:
                    self.adb.tap_center(expansion_item['box'])
                    return
                go_back(self.adb, self.recognizer, screenshot)
                return

        # 循环滑动查找沙漏图标
        max_attempts = 10
        last_texts = set()

        for attempt in range(max_attempts):
            if attempt > 0:
                print(f"  -> 第{attempt}次滑动查找沙漏")
                self.adb.swipe_up(ratio=0.21)  # 约 400/1920
                time.sleep(1.2)
                screenshot = self.adb.screenshot()
                if screenshot:
                    ocr_results = self.recognizer.ocr_full_screen(screenshot)

            # 检测是否有弹窗遮挡
            if detect_and_close_popup(self.adb, ocr_results):
                return  # 返回主循环重新检测页面

            # 查找沙漏图标
            shalou_box = self.recognizer.find_template(screenshot, "shalou", threshold=0.6)
            if shalou_box:
                print("  -> 找到沙漏，点击未完成牌组")
                self.adb.tap_center(shalou_box)
                return

            # 收集当前文字用于底部检测
            current_texts = set(item['text'].strip() for item in ocr_results)

            # 检测是否到底
            if attempt > 0 and current_texts == last_texts:
                print("  -> 已滑动到底部，未找到沙漏")
                break

            last_texts = current_texts

        # 没有沙漏，标记当前卡包为完成
        if current_level and current_pack_id:
            self.state.set_pack_complete(current_level, current_pack_id, True)

        # 点击扩充组查看更多卡包
        expansion_item = find_text_by_variants(ocr_results, "expansion_button")
        if expansion_item:
            print("  -> 点击擴充組查看更多卡包")
            self.adb.tap_center(expansion_item['box'])
            return

        # 都没找到，返回
        print("  -> 当前等级已完成，返回")
        go_back(self.adb, self.recognizer, screenshot)

    def _detect_level_from_ocr(self, ocr_results: List[Dict]) -> Optional[str]:
        """从 OCR 结果中检测当前等级"""
        for item in ocr_results:
            text = item['text'].strip()
            for level in config.BATTLE_LEVELS:
                if level in text:
                    return level
        return None

    def _extract_pack_name(self, ocr_results: List[Dict]) -> Optional[str]:
        """从 OCR 结果中提取卡包名称

        使用 config.DECK_KEYWORD 匹配格式如:
        - 中文: "毽子花牌組（高級擴充包ex）" -> 提取 "高級擴充包ex"
        - 英文: "Carnivine Deck (Triumphant Light)" -> 提取 "Triumphant Light"
        - 跨行: "Darkrai Deck" + "(Space-Time Smackdown)" -> 提取 "Space-Time Smackdown"
        """
        deck_keyword = config.DECK_KEYWORD

        for item in ocr_results:
            text = item['text'].strip()

            # 情况1: 同一行包含完整格式
            pattern = rf'{re.escape(deck_keyword)}\s*[（(](.+?)[）)]'
            match = re.search(pattern, text)
            if match:
                return match.group(1).strip()

            # 情况2: 当前行以 Deck 结尾，卡包名在下一行
            if text.endswith(deck_keyword):
                item_y = (item['box'][1] + item['box'][3]) // 2
                for other_item in ocr_results:
                    other_text = other_item['text'].strip()
                    other_y = (other_item['box'][1] + other_item['box'][3]) // 2
                    if 0 < other_y - item_y < 150 and (other_text.startswith('(') or other_text.startswith('（')):
                        pack_match = re.search(r'[（(](.+?)[）)]', other_text)
                        if pack_match:
                            return pack_match.group(1).strip()

        return None
