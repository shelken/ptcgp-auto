"""
动作处理器 - 处理各种界面的操作
"""

import re
import time
from typing import Optional, Dict, List

import config
from adb_controller import AdbController
from recognizer import Recognizer
from state_manager import StateManager


class ActionHandler:
    """动作处理器"""

    def __init__(
        self,
        adb: AdbController,
        recognizer: Recognizer,
        state: StateManager
    ):
        self.adb = adb
        self.recognizer = recognizer
        self.state = state
        self.current_pack_name = None  # 当前卡包名称
        self.tried_expansion_progress = set()  # 本轮已尝试的进度文本（如 "29/114"）

    def execute(self, action: str, screenshot, match_info: Dict):
        """执行动作

        Args:
            action: 动作名称
            screenshot: 当前截图
            match_info: 匹配信息
        """
        handler = getattr(self, f"action_{action}", None)
        if handler:
            handler(screenshot, match_info)
        else:
            print(f"  -> 未知动作: {action}")

    # ==================== 基础动作 ====================

    def action_click_identifier(self, screenshot, match_info: Dict):
        """点击识别到的文字位置"""
        box = match_info.get("box")
        if box:
            print(f"  -> 点击: {match_info.get('identifier', 'unknown')}")
            self.adb.tap_center(box)

    def action_click_continue(self, screenshot, match_info: Dict):
        """点击屏幕中央继续"""
        print("  -> 点击屏幕继续")
        self.adb.tap(config.SCREEN_WIDTH // 2, config.SCREEN_HEIGHT // 2)

    def action_click_cancel(self, screenshot, match_info: Dict):
        """点击取消按钮（用于战败弹窗等）"""
        ocr_results = match_info.get("ocr_results", [])
        for item in ocr_results:
            text = item['text'].strip()
            if text == "取消":
                print("  -> 点击取消")
                self.adb.tap_center(item['box'])
                return
        # 如果没找到取消，尝试点击屏幕继续
        print("  -> 未找到取消按钮，点击屏幕继续")
        self.adb.tap(config.SCREEN_WIDTH // 2, config.SCREEN_HEIGHT // 2)

    def action_click_template(self, screenshot, match_info: Dict):
        """点击模板位置"""
        box = match_info.get("box")
        if box:
            print(f"  -> 点击模板: {match_info.get('template', 'unknown')}")
            self.adb.tap_center(box)

    def action_wait(self, screenshot, match_info: Dict):
        """等待（对战中）"""
        print("  -> 对战中，等待...")
        time.sleep(config.WAIT_BATTLE_CHECK_INTERVAL)

    # ==================== 对战相关 ====================

    def action_start_battle(self, screenshot, match_info: Dict):
        """开始对战 - 先开启自动，再点击对战按钮"""
        ocr_results = match_info.get("ocr_results", [])

        # 检查自动模式状态
        auto_box = None
        has_off = False

        for item in ocr_results:
            text = item['text'].strip().upper()
            if '自動' in item['text'] or 'AUTO' in text:
                auto_box = item['box']
            if 'OFF' in text:
                has_off = True

        # 如果自动模式是 OFF，先点击开启
        if auto_box and has_off:
            print("  -> 开启自动模式")
            self.adb.tap_center(auto_box)
            time.sleep(0.5)

        # 点击对战按钮
        battle_box = match_info.get("box")
        if battle_box:
            print("  -> 点击对战")
            self.adb.tap_center(battle_box)

    # ==================== 等级选择 ====================

    def action_select_level(self, screenshot, match_info: Dict):
        """选择未完成的等级（按配置顺序优先）"""
        ocr_results = match_info.get("ocr_results", [])

        # 按优先级逐个查找等级
        for level in config.BATTLE_LEVELS:
            # 跳过已标记为完成的等级
            if self.state.is_level_complete(level):
                continue

            # 尝试在当前屏幕和滑动后查找该等级
            found = self._find_and_click_level(level, ocr_results, screenshot)
            if found:
                return

        print("  -> 未找到未完成的等级，尝试返回")
        self._go_back(screenshot)

    def _find_and_click_level(self, level: str, ocr_results: List[Dict], screenshot) -> bool:
        """查找并点击指定等级，如果需要会滑动查找

        Returns:
            True 如果找到并点击了，False 如果没找到
        """
        for attempt in range(3):  # 最多尝试3次（包括滑动）
            if attempt > 0:
                # 滑动查看更多等级
                print(f"  -> 滑动查找 {level} (第{attempt}次)")
                self.adb.swipe_up(distance=400)
                time.sleep(0.8)
                # 重新截图和OCR
                screenshot = self.adb.screenshot()
                if screenshot:
                    ocr_results = self.recognizer.ocr_full_screen(screenshot)
                else:
                    continue

            # 在当前 OCR 结果中查找该等级
            for item in ocr_results:
                text = item['text'].strip()
                if level in text:
                    # 检查该等级是否有进度数字（未完成）
                    level_y = (item['box'][1] + item['box'][3]) // 2

                    for other_item in ocr_results:
                        other_y = (other_item['box'][1] + other_item['box'][3]) // 2
                        # 同一行附近（增大容差到150像素）
                        if abs(other_y - level_y) < 150:
                            other_text = other_item['text'].strip()

                            # 检查是否显示 Complete
                            if 'COMPLETE' in other_text.upper():
                                self.state.set_level_complete(level, True)
                                return False  # 该等级已完成，返回让外层继续下一个等级

                            # 有进度数字表示未完成
                            if re.search(r'\d+\s*/\s*\d+', other_text):
                                print(f"  -> 选择等级: {level} ({other_text})")
                                self.state.set_current_level(level)
                                self.adb.tap_center(item['box'])
                                return True

        # 滑动多次后仍未找到该等级
        return False

    # ==================== 单人对战主页 ====================

    def action_find_incomplete(self, screenshot, match_info: Dict):
        """在单人对战主页寻找未完成任务"""
        ocr_results = match_info.get("ocr_results", [])

        # 查找分级对战入口（优先）
        for item in ocr_results:
            text = item['text'].strip()
            if '分級對戰' in text:
                print("  -> 进入分级对战")
                self.adb.tap_center(item['box'])
                return

        # 查找有进度数字的任务
        for item in ocr_results:
            text = item['text'].strip()
            if re.search(r'\d+\s*/\s*\d+', text):
                print(f"  -> 找到未完成任务: {text}")
                self.adb.tap_center(item['box'])
                return

        print("  -> 未找到可操作的任务")

    def action_click_solo_battle(self, screenshot, match_info: Dict):
        """在主菜单点击单人对战"""
        ocr_results = match_info.get("ocr_results", [])

        # 查找单人对战入口
        for item in ocr_results:
            text = item['text'].strip()
            if '單人對戰' in text:
                print("  -> 点击单人对战")
                self.adb.tap_center(item['box'])
                return

        print("  -> 未找到单人对战入口")

    # ==================== 牌组列表 ====================

    def action_handle_deck_list(self, screenshot, match_info: Dict):
        """处理牌组列表页面"""
        ocr_results = match_info.get("ocr_results", [])
        current_level = self.state.get_current_level()

        # 如果 current_level 未设置，尝试从页面上识别
        if not current_level:
            current_level = self._detect_level_from_ocr(ocr_results)
            if current_level:
                print(f"  [等级] 从页面识别: {current_level}")
                self.state.set_current_level(current_level)

        # 尝试识别当前卡包名称（从标题中提取）
        pack_name = self._extract_pack_name(ocr_results)
        if pack_name:
            self.current_pack_name = pack_name
            print(f"  [卡包] {pack_name}")

            # 检查是否已标记为完成 - 进入扩充组选择其他卡包
            if current_level and self.state.is_pack_complete(current_level, pack_name):
                print(f"  -> {pack_name} 在 {current_level} 已完成，进入扩充组选择其他卡包")
                # 点击擴充組进入扩充组选择页面
                for item in ocr_results:
                    text = item['text'].strip()
                    if '擴充組' in text:
                        self.adb.tap_center(item['box'])
                        return
                # 如果没找到擴充組按钮，再返回
                self._go_back(screenshot)
                return

        # 优先查找沙漏图标（有未完成的牌组）
        shalou_box = self.recognizer.find_template(screenshot, "shalou", threshold=0.6)
        if shalou_box:
            print("  -> 找到沙漏，点击未完成牌组")
            self.adb.tap_center(shalou_box)
            return

        # 没有沙漏，尝试滑动查看更多
        print("  -> 未找到沙漏，尝试滑动查看更多")
        self.adb.swipe_up(distance=400)
        time.sleep(0.8)

        # 再次检查
        screenshot2 = self.adb.screenshot()
        if screenshot2:
            shalou_box = self.recognizer.find_template(screenshot2, "shalou", threshold=0.6)
            if shalou_box:
                print("  -> 滑动后找到沙漏")
                self.adb.tap_center(shalou_box)
                return

        # 没有沙漏，标记当前卡包为完成
        if current_level and self.current_pack_name:
            self.state.set_pack_complete(current_level, self.current_pack_name, True)
            print(f"  [状态] 标记 {self.current_pack_name} 在 {current_level} 完成")

        # 点击扩充组查看更多卡包
        for item in ocr_results:
            text = item['text'].strip()
            if '擴充組' in text:
                print("  -> 点击擴充組查看更多卡包")
                self.adb.tap_center(item['box'])
                return

        # 都没找到，返回
        print("  -> 当前等级已完成，返回")
        self._go_back(screenshot)

    # ==================== 扩充组选择 ====================

    def action_handle_expansion_select(self, screenshot, match_info: Dict):
        """处理扩充组选择页面 - 选择未完成的卡包"""
        ocr_results = match_info.get("ocr_results", [])
        current_series = self.state.get_current_series()
        current_level = self.state.get_current_level()

        # 收集所有进度数字和对应位置
        progress_items = []
        has_series_button = {"A": None, "B": None}

        for item in ocr_results:
            text = item['text'].strip()

            # 记录系列按钮位置
            if 'A系列' in text:
                has_series_button["A"] = item['box']
            if 'B系列' in text:
                has_series_button["B"] = item['box']

            # 跳过标题和系列选择
            if '選擇擴充組' in text or '系列' in text:
                continue

            # 检查是否是进度数字（如 "21/30"）
            progress_match = re.search(r'(\d+)\s*/\s*(\d+)', text)
            if progress_match:
                current_val = int(progress_match.group(1))
                total = int(progress_match.group(2))
                # 规范化进度文本作为标识
                progress_key = f"{current_val}/{total}"

                if current_val < total:  # 未完成
                    # 检查是否已在本轮尝试过
                    if progress_key in self.tried_expansion_progress:
                        print(f"  [跳过] {progress_key} (已尝试)")
                        continue

                    progress_items.append({
                        'text': text,
                        'box': item['box'],
                        'remaining': total - current_val,
                        'progress_key': progress_key
                    })

        # 按剩余数量排序，优先处理剩余多的
        progress_items.sort(key=lambda x: x['remaining'], reverse=True)

        if progress_items:
            item = progress_items[0]
            print(f"  -> 选择未完成卡包: {item['progress_key']} (剩余 {item['remaining']})")
            # 记录已尝试的进度
            self.tried_expansion_progress.add(item['progress_key'])
            self.adb.tap_center(item['box'])
            return

        # 没有找到未完成的，尝试滑动
        print("  -> 当前页面都已尝试或 CLEAR，尝试滑动查看更多")
        self.adb.swipe_up(distance=400)
        time.sleep(0.8)

        # 再次检查（滑动后重新识别）
        screenshot2 = self.adb.screenshot()
        if screenshot2:
            ocr_results2 = self.recognizer.ocr_full_screen(screenshot2)
            for item in ocr_results2:
                text = item['text'].strip()
                # 跳过标题和系列选择
                if '選擇擴充組' in text or '系列' in text:
                    continue

                progress_match = re.search(r'(\d+)\s*/\s*(\d+)', text)
                if progress_match:
                    current_val = int(progress_match.group(1))
                    total = int(progress_match.group(2))
                    progress_key = f"{current_val}/{total}"

                    if current_val < total:
                        # 检查是否已尝试过
                        if progress_key in self.tried_expansion_progress:
                            continue

                        print(f"  -> 滑动后找到未完成卡包: {progress_key}")
                        self.tried_expansion_progress.add(progress_key)
                        self.adb.tap_center(item['box'])
                        return

        # 尝试切换到另一个系列
        other_series = "B" if current_series == "A" else "A"
        if has_series_button[other_series]:
            print(f"  -> 当前系列 {current_series} 已完成，切换到 {other_series} 系列")
            self.state.set_current_series(other_series)
            # 切换系列后清空已尝试记录
            self.tried_expansion_progress.clear()
            self.adb.tap_center(has_series_button[other_series])
            return

        # 全部完成，关闭页面
        print("  -> 所有卡包已完成，关闭扩充组选择")
        self.state.set_current_series("A")
        # 清空已尝试记录，准备下一轮
        self.tried_expansion_progress.clear()
        self._close_expansion_select(screenshot, ocr_results)

    # ==================== 辅助方法 ====================

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

        格式如: "毽子花牌組（高級擴充包ex）" -> 提取 "高級擴充包ex"
        """
        for item in ocr_results:
            text = item['text'].strip()
            # 匹配 "xxx牌組（卡包名）" 格式
            match = re.search(r'牌組[（(](.+?)[）)]', text)
            if match:
                return match.group(1).strip()
        return None

    def _go_back(self, screenshot):
        """返回上一页"""
        if screenshot:
            back_btn = self.recognizer.find_template(screenshot, "btn_back", threshold=0.6)
            if back_btn:
                self.adb.tap_center(back_btn)
                return
        self.adb.back()

    def _close_expansion_select(self, screenshot, ocr_results: List[Dict]):
        """关闭扩充组选择页面"""
        # 点击 X 按钮关闭
        for item in ocr_results:
            text = item['text'].strip()
            if text in ['×', 'X', 'x', '✕']:
                self.adb.tap_center(item['box'])
                return

        # 尝试模板匹配 X 按钮
        close_btn = self.recognizer.find_template(screenshot, "btn_close", threshold=0.6)
        if close_btn:
            self.adb.tap_center(close_btn)
            return

        self._go_back(screenshot)
