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
        self.needs_state_init = state.needs_initialization()  # 是否需要初始化状态

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
        cancel_variants = config.TEXT_VARIANTS.get("cancel", ["取消", "Cancel"])
        for item in ocr_results:
            text = item['text'].strip()
            if text in cancel_variants:
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

        # 如果需要初始化状态且当前等级未设置，返回上级页面
        if self.needs_state_init and not self.state.get_current_level():
            print("  -> 需要初始化状态，返回上级页面")
            self._go_back(screenshot)
            return

        # 检查是否应该切换到更高优先级的等级
        if self._should_switch_to_higher_priority_level():
            print("  -> 返回上级页面以选择更高优先级等级")
            self._go_back(screenshot)
            return

        # 检查自动模式状态
        auto_box = None
        has_off = False
        auto_variants = config.TEXT_VARIANTS.get("auto", ["自動", "Auto", "AUTO"])

        for item in ocr_results:
            text = item['text'].strip()
            text_upper = text.upper()
            for variant in auto_variants:
                if variant in text or variant.upper() in text_upper:
                    auto_box = item['box']
                    break
            if 'OFF' in text_upper:
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

        # 如果需要初始化，先同步所有等级状态
        if self.needs_state_init:
            self._sync_level_complete_status(ocr_results, screenshot)
            self.needs_state_init = False

        # 检查是否应该切换到更高优先级的等级（基于 state 文件中的状态）
        if self._should_switch_to_higher_priority_level():
            print("  -> 返回上级页面以选择更高优先级等级")
            self.state.set_current_level(None)
            self._go_back(screenshot)
            return

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
        max_attempts = 10  # 最多滑动次数
        last_texts = set()  # 上次看到的文字集合

        for attempt in range(max_attempts):
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

            # 收集当前文字
            current_texts = set(item['text'].strip() for item in ocr_results)

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

            # 检测是否到底（内容不变）
            if attempt > 0 and current_texts == last_texts:
                print(f"  -> 已滑动到底部，未找到 {level}")
                break

            last_texts = current_texts

        # 滑动多次后仍未找到该等级
        return False

    # ==================== 单人对战主页 ====================

    def action_find_incomplete(self, screenshot, match_info: Dict):
        """在单人对战主页寻找未完成任务"""
        ocr_results = match_info.get("ocr_results", [])

        # 查找分级对战入口（优先，使用 TEXT_VARIANTS）
        ranked_variants = config.TEXT_VARIANTS.get("ranked_battle", [])
        for item in ocr_results:
            text = item['text'].strip()
            for variant in ranked_variants:
                if variant in text or text in variant:
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

        # 查找单人对战入口（使用 TEXT_VARIANTS）
        solo_variants = config.TEXT_VARIANTS.get("solo_battle", [])
        for item in ocr_results:
            text = item['text'].strip()
            for variant in solo_variants:
                if variant in text or text in variant:
                    print("  -> 点击单人对战")
                    self.adb.tap_center(item['box'])
                    return

        print("  -> 未找到单人对战入口")

    # ==================== 牌组列表 ====================

    def action_handle_deck_list(self, screenshot, match_info: Dict):
        """处理牌组列表页面"""
        ocr_results = match_info.get("ocr_results", [])
        current_level = self.state.get_current_level()

        # 如果需要初始化状态且当前等级未设置，返回上级页面
        if self.needs_state_init and not current_level:
            print("  -> 需要初始化状态，返回上级页面")
            self._go_back(screenshot)
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
            self._go_back(screenshot)
            return

        # 检查是否应该切换到更高优先级的等级
        if self._should_switch_to_higher_priority_level():
            print("  -> 返回上级页面以选择更高优先级等级")
            self._go_back(screenshot)
            return

        # 尝试识别当前卡包名称（从标题中提取）
        pack_name = self._extract_pack_name(ocr_results)
        if pack_name:
            self.current_pack_name = pack_name
            print(f"  [卡包] {pack_name}")

            # 检查是否已标记为完成 - 进入扩充组选择其他卡包
            if current_level and self.state.is_pack_complete(current_level, pack_name):
                print(f"  -> {pack_name} 在 {current_level} 已完成，进入扩充组选择其他卡包")
                # 点击擴充組进入扩充组选择页面
                expansion_variants = config.TEXT_VARIANTS.get("expansion_button", ["擴充組", "Expansion"])
                for item in ocr_results:
                    text = item['text'].strip()
                    for variant in expansion_variants:
                        if variant in text:
                            self.adb.tap_center(item['box'])
                            return
                # 如果没找到擴充組按钮，再返回
                self._go_back(screenshot)
                return

        # 循环滑动查找沙漏图标
        max_attempts = 10
        last_texts = set()

        for attempt in range(max_attempts):
            if attempt > 0:
                print(f"  -> 第{attempt}次滑动查找沙漏")
                self.adb.swipe_up(distance=400)
                time.sleep(0.8)
                screenshot = self.adb.screenshot()
                if screenshot:
                    ocr_results = self.recognizer.ocr_full_screen(screenshot)

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
        if current_level and self.current_pack_name:
            self.state.set_pack_complete(current_level, self.current_pack_name, True)
            print(f"  [状态] 标记 {self.current_pack_name} 在 {current_level} 完成")

        # 点击扩充组查看更多卡包
        expansion_variants = config.TEXT_VARIANTS.get("expansion_button", ["擴充組", "Expansion"])
        for item in ocr_results:
            text = item['text'].strip()
            for variant in expansion_variants:
                if variant in text:
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

        # 检查是否应该切换到更高优先级的等级
        if self._should_switch_to_higher_priority_level():
            print("  -> 返回上级页面以选择更高优先级等级")
            self._close_expansion_select(screenshot, ocr_results)
            return

        max_scroll_attempts = 5  # 最多滑动5次
        last_progress_keys = set()  # 上一次看到的进度数字集合
        has_series_button = {"A": None, "B": None}
        seen_clear = False  # 是否看到过 CLEAR!
        seen_incomplete = False  # 是否看到过未完成的进度

        for scroll_attempt in range(max_scroll_attempts):
            if scroll_attempt > 0:
                print(f"  -> 第{scroll_attempt}次滑动查找卡包")
                self.adb.swipe_up(distance=400)
                time.sleep(0.8)
                screenshot = self.adb.screenshot()
                if screenshot:
                    ocr_results = self.recognizer.ocr_full_screen(screenshot)

            # 收集当前屏幕的进度数字
            current_progress_keys = set()
            progress_items = []

            for item in ocr_results:
                text = item['text'].strip()

                # 记录系列按钮位置
                series_a_variants = config.TEXT_VARIANTS.get("series_a", ["A系列", "Series A"])
                series_b_variants = config.TEXT_VARIANTS.get("series_b", ["B系列", "Series B"])
                for variant in series_a_variants:
                    if variant in text:
                        has_series_button["A"] = item['box']
                        break
                for variant in series_b_variants:
                    if variant in text:
                        has_series_button["B"] = item['box']
                        break

                # 跳过标题和系列选择
                select_expansion_variants = config.TEXT_VARIANTS.get("select_expansion", ["選擇擴充組", "Select Expansion"])
                series_variants = config.TEXT_VARIANTS.get("series", ["系列", "Series"])
                skip = False
                for variant in select_expansion_variants + series_variants:
                    if variant in text:
                        skip = True
                        break
                if skip:
                    continue

                # 检查是否是 CLEAR!（当前等级已完成）
                if 'CLEAR' in text.upper():
                    seen_clear = True
                    continue

                # 检查是否是进度数字（如 "21/30"）
                progress_match = re.search(r'(\d+)\s*/\s*(\d+)', text)
                if progress_match:
                    current_val = int(progress_match.group(1))
                    total = int(progress_match.group(2))
                    progress_key = f"{current_val}/{total}"
                    item_x = (item['box'][0] + item['box'][2]) // 2
                    item_y = (item['box'][1] + item['box'][3]) // 2

                    current_progress_keys.add(progress_key)

                    # 收集进度信息，稍后按行分组判断左右
                    progress_items.append({
                        'text': text,
                        'box': item['box'],
                        'x': item_x,
                        'y': item_y,
                        'current_val': current_val,
                        'total': total,
                        'progress_key': progress_key
                    })

            # 按 Y 坐标分组，找出每行中 x 较小的（当前等级进度）
            left_progress_items = []
            if progress_items:
                # 按 Y 坐标排序分组
                progress_items.sort(key=lambda x: x['y'])
                row_items = []
                last_y = None

                for item in progress_items:
                    if last_y is None or abs(item['y'] - last_y) < 100:
                        row_items.append(item)
                    else:
                        # 新的一行，处理上一行
                        if row_items:
                            # 取 x 最小的作为当前等级进度
                            left_item = min(row_items, key=lambda x: x['x'])
                            left_progress_items.append(left_item)
                        row_items = [item]
                    last_y = item['y']

                # 处理最后一行
                if row_items:
                    left_item = min(row_items, key=lambda x: x['x'])
                    left_progress_items.append(left_item)

            # 找到未完成的卡包（只看左侧进度）
            incomplete_items = []
            for item in left_progress_items:
                if item['current_val'] < item['total']:
                    seen_incomplete = True
                    if item['progress_key'] not in self.tried_expansion_progress:
                        incomplete_items.append({
                            'text': item['text'],
                            'box': item['box'],
                            'remaining': item['total'] - item['current_val'],
                            'progress_key': item['progress_key']
                        })

            if incomplete_items:
                incomplete_items.sort(key=lambda x: x['remaining'], reverse=True)
                item = incomplete_items[0]
                print(f"  -> 选择未完成卡包: {item['progress_key']} (剩余 {item['remaining']})")
                self.tried_expansion_progress.add(item['progress_key'])
                self.adb.tap_center(item['box'])
                return

            # 检测是否到底（没有新内容）
            if scroll_attempt > 0 and current_progress_keys == last_progress_keys:
                print(f"  -> 已滑动到底部（第{scroll_attempt}次滑动后无新内容）")
                break

            last_progress_keys = current_progress_keys

        # 尝试切换到另一个系列
        other_series = "B" if current_series == "A" else "A"
        if has_series_button[other_series]:
            print(f"  -> 当前系列 {current_series} 已完成，切换到 {other_series} 系列")
            self.state.set_current_series(other_series)
            # 切换系列后清空已尝试记录
            self.tried_expansion_progress.clear()
            self.adb.tap_center(has_series_button[other_series])
            return

        # 所有系列都遍历完了
        # 如果看到过 CLEAR! 但没有看到未完成的进度，说明当前等级完成
        if seen_clear and not seen_incomplete and current_level:
            print(f"  -> 所有卡包当前等级都已 CLEAR，标记 {current_level} 为完成")
            self.state.set_level_complete(current_level, True)
            self.state.set_current_level(None)

        # 关闭页面
        print("  -> 关闭扩充组选择")
        self.state.set_current_series("A")
        # 清空已尝试记录，准备下一轮
        self.tried_expansion_progress.clear()
        self._close_expansion_select(screenshot, ocr_results)

    # ==================== 辅助方法 ====================

    def _should_switch_to_higher_priority_level(self) -> bool:
        """检查是否应该切换到更高优先级的等级

        Returns:
            True 如果当前等级不是最高优先级的未完成等级，应该返回重新选择
        """
        current_level = self.state.get_current_level()
        if not current_level:
            return False

        # 找到最高优先级的未完成等级
        for level in config.BATTLE_LEVELS:
            if not self.state.is_level_complete(level):
                # 这是最高优先级的未完成等级
                if level != current_level:
                    print(f"  [优先级检查] 当前 {current_level}，但 {level} 未完成且优先级更高")
                    return True
                else:
                    # 当前等级就是最高优先级，不需要切换
                    return False

        return False

    def _sync_level_complete_status(self, ocr_results: List[Dict], screenshot):
        """同步所有等级的完成状态"""
        print("  [初始化] 正在同步等级完成状态...")

        synced_levels = set()
        max_attempts = 10
        last_texts = set()

        for attempt in range(max_attempts):
            if attempt > 0:
                self.adb.swipe_up(distance=400)
                time.sleep(0.8)
                screenshot = self.adb.screenshot()
                if screenshot:
                    ocr_results = self.recognizer.ocr_full_screen(screenshot)

            # 收集当前文字用于底部检测
            current_texts = set(item['text'].strip() for item in ocr_results)

            for item in ocr_results:
                text = item['text'].strip()
                for level in config.BATTLE_LEVELS:
                    if level in text and level not in synced_levels:
                        level_y = (item['box'][1] + item['box'][3]) // 2
                        is_complete = False
                        # 检查同一行是否有 COMPLETE
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

            # 检测是否到底
            if attempt > 0 and current_texts == last_texts:
                print("  [初始化] 已滑动到底部")
                break

            last_texts = current_texts

        # 滑动回顶部
        self.adb.swipe_down(distance=800)
        time.sleep(0.5)

        print(f"  [初始化] 同步完成，共 {len(synced_levels)} 个等级")

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
