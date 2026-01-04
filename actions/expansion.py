"""扩充组选择动作模块"""

import re
import time
from typing import Dict, List, Set, Optional, Callable

import config
from .utils import close_popup, detect_and_close_popup


class ExpansionActions:
    """扩充组选择相关动作处理"""

    def __init__(self, adb, recognizer, state, should_switch_checker: Callable[[], bool]):
        self.adb = adb
        self.recognizer = recognizer
        self.state = state
        self._should_switch_to_higher_priority_level = should_switch_checker

    def handle_expansion_select(
        self,
        screenshot,
        match_info: Dict,
        tried_expansion_series: Set[str],
        set_tried_expansion_series: Callable[[Set[str]], None],
        set_all_packs_checked: Callable[[bool], None],
        set_current_pack_id: Callable[[str], None]
    ):
        """处理扩充组选择页面 - 选择未完成的卡包"""
        ocr_results = match_info.get("ocr_results", [])
        current_level = self.state.get_current_level()

        # 检查是否应该切换到更高优先级的等级
        if self._should_switch_to_higher_priority_level():
            print("  -> 返回上级页面以选择更高优先级等级")
            set_tried_expansion_series(set())
            self._close_expansion_select(screenshot, ocr_results)
            return

        # 根据 tried_expansion_series 判断状态
        if not tried_expansion_series:
            current_series = "init"
        elif "A" in tried_expansion_series and "B" not in tried_expansion_series:
            current_series = "B"
        elif "A" in tried_expansion_series and "B" in tried_expansion_series:
            print("  -> 所有系列都已检查，关闭扩充组选择")
            set_tried_expansion_series(set())
            set_all_packs_checked(True)
            self._close_expansion_select(screenshot, ocr_results)
            return
        else:
            current_series = "A"

        last_progress_keys = set()
        scroll_count = 0
        has_series_button = {"A": None, "B": None}

        # 获取 patterns（只获取一次，避免循环内重复获取）
        series_a_patterns = config.TEXT_PATTERNS.get("series_a", [])
        series_b_patterns = config.TEXT_PATTERNS.get("series_b", [])
        skip_titles = config.TEXT_PATTERNS.get("skip_titles", [])

        # 先扫描一遍找到系列按钮
        for item in ocr_results:
            text = item['text'].strip()
            for pattern in series_a_patterns:
                if pattern in text:
                    has_series_button["A"] = item['box']
                    break
            for pattern in series_b_patterns:
                if pattern in text:
                    has_series_button["B"] = item['box']
                    break

        # 如果是 init 状态，先点击 A 按钮确保在 A 系列
        if current_series == "init":
            if has_series_button["A"]:
                print("  -> 点击 A 系列按钮确保在 A 系列")
                new_series = tried_expansion_series.copy()
                new_series.add("clicked_A")
                set_tried_expansion_series(new_series)
                self.adb.tap_center(has_series_button["A"])
                return
            else:
                current_series = "A"
                new_series = tried_expansion_series.copy()
                new_series.add("clicked_A")
                set_tried_expansion_series(new_series)

        # 如果刚点击了 A 按钮，现在开始遍历 A 系列
        if "clicked_A" in tried_expansion_series and "A" not in tried_expansion_series:
            current_series = "A"

        while True:
            if scroll_count > 0:
                print(f"  -> 第{scroll_count}次滑动查找卡包")
                self.adb.swipe_up(ratio=0.21)  # 约 400/1920
                time.sleep(1.2)
                screenshot = self.adb.screenshot()
                if screenshot:
                    ocr_results = self.recognizer.ocr_full_screen(screenshot)

            # 检测是否有弹窗遮挡
            if detect_and_close_popup(self.adb, ocr_results):
                return  # 返回主循环重新检测页面

            # 收集当前屏幕的进度数字
            current_progress_keys = set()
            progress_items = []

            for item in ocr_results:
                text = item['text'].strip()

                # 记录系列按钮位置
                for pattern in series_a_patterns:
                    if pattern in text:
                        has_series_button["A"] = item['box']
                        break
                for pattern in series_b_patterns:
                    if pattern in text:
                        has_series_button["B"] = item['box']
                        break

                # 跳过标题和系列选择
                skip = False
                for pattern in skip_titles:
                    if pattern in text:
                        skip = True
                        break
                if skip:
                    continue

                # 检查是否是 CLEAR!
                if 'CLEAR' in text.upper():
                    continue

                # 检查是否是进度数字
                progress_match = re.search(r'(\d+)\s*/\s*(\d+)', text)
                if progress_match:
                    current_val = int(progress_match.group(1))
                    total = int(progress_match.group(2))
                    progress_key = f"{current_val}/{total}"
                    item_x = (item['box'][0] + item['box'][2]) // 2
                    item_y = (item['box'][1] + item['box'][3]) // 2

                    current_progress_keys.add(progress_key)
                    progress_items.append({
                        'text': text, 'box': item['box'],
                        'x': item_x, 'y': item_y,
                        'current_val': current_val, 'total': total,
                        'progress_key': progress_key
                    })

            # 按 Y 坐标分组
            row_data = self._group_progress_by_row(progress_items)

            # 找到未完成的卡包
            incomplete_items = []
            if config.DEBUG:
                print(f"  [DEBUG] row_data 共 {len(row_data)} 行")

            for row in row_data:
                right = row['right']  # 卡片收集进度
                left = row['left']    # 牌组完成进度
                if not right:
                    continue

                # 如果左侧为空或者是 CLEAR，跳过该卡包（已完成所有牌组）
                if not left:
                    if config.DEBUG:
                        print(f"  [DEBUG] 跳过: 左侧进度为空 (right={right['progress_key']})")
                    continue

                # 生成组合 ID: 系列_左分母_右分母 (如 a_20_81)
                series_prefix = current_series.lower()
                left_total = str(left['total'])
                right_total = str(right['total'])
                pack_id = f"{series_prefix}_{left_total}_{right_total}"

                if config.DEBUG:
                    left_str = f"{left['current_val']}/{left['total']}"
                    print(f"  [DEBUG] 检查卡包: left={left_str}, right={right['current_val']}/{right['total']}, pack_id={pack_id}")

                if current_level and self.state.is_pack_complete(current_level, pack_id):
                    if config.DEBUG:
                        print(f"  [DEBUG]   -> 已标记为完成，跳过")
                    continue

                # 使用左侧进度判断是否未完成
                if left['current_val'] < left['total']:
                    incomplete_items.append({
                        'text': f"{left['progress_key']} | {right['progress_key']}",
                        'box': left['box'],
                        'remaining': left['total'] - left['current_val'],
                        'pack_id': pack_id,
                        'progress_key': f"{left['progress_key']} | {right['progress_key']}"
                    })
                    if config.DEBUG:
                        print(f"  [DEBUG]   -> 未完成，加入候选")

            if incomplete_items:
                incomplete_items.sort(key=lambda x: x['remaining'], reverse=True)
                item = incomplete_items[0]
                print(f"  -> 选择未完成卡包: {item['progress_key']} (pack_id={item['pack_id']}, 剩余 {item['remaining']})")
                set_current_pack_id(item['pack_id'])
                set_tried_expansion_series(set())
                set_all_packs_checked(False)
                self.adb.tap_center(item['box'])
                return

            # 检测是否到底
            if scroll_count > 0 and current_progress_keys == last_progress_keys:
                print(f"  -> 已滑动到底部（第{scroll_count}次滑动后无新内容）")
                break

            last_progress_keys = current_progress_keys
            scroll_count += 1

        # 当前系列没有未完成的卡包
        new_series = tried_expansion_series.copy()
        new_series.add(current_series)
        new_series.discard("clicked_A")
        set_tried_expansion_series(new_series)

        # 尝试切换到另一个系列
        other_series = "B" if current_series == "A" else "A"
        if other_series not in tried_expansion_series and has_series_button[other_series]:
            print(f"  -> {current_series} 系列无可用卡包，切换到 {other_series} 系列")
            self.adb.tap_center(has_series_button[other_series])
            return

        # 所有系列都遍历完了
        set_tried_expansion_series(set())
        set_all_packs_checked(True)
        print("  -> 所有系列都已检查，关闭扩充组选择")
        self._close_expansion_select(screenshot, ocr_results)

    def _group_progress_by_row(self, progress_items: List[Dict]) -> List[Dict]:
        """按 Y 坐标分组进度项"""
        if not progress_items:
            return []

        progress_items.sort(key=lambda x: x['y'])
        row_data = []
        row_items = []
        row_start_y = None

        for item in progress_items:
            if row_start_y is None or abs(item['y'] - row_start_y) < 100:
                row_items.append(item)
                if row_start_y is None:
                    row_start_y = item['y']
            else:
                if len(row_items) >= 2:
                    row_items.sort(key=lambda x: x['x'])
                    row_data.append({'left': row_items[0], 'right': row_items[-1]})
                elif len(row_items) == 1:
                    row_data.append({'left': None, 'right': row_items[0]})
                row_items = [item]
                row_start_y = item['y']

        if len(row_items) >= 2:
            row_items.sort(key=lambda x: x['x'])
            row_data.append({'left': row_items[0], 'right': row_items[-1]})
        elif len(row_items) == 1:
            row_data.append({'left': None, 'right': row_items[0]})

        return row_data

    def _close_expansion_select(self, screenshot, ocr_results: List[Dict]):
        """关闭扩充组选择页面"""
        close_popup(self.adb, self.recognizer, screenshot, ocr_results)
