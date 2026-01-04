"""对战相关动作模块"""

import time
from typing import Dict, Callable

import config
from .utils import go_back


class BattleActions:
    """对战相关动作处理"""

    def __init__(self, adb, recognizer, state, should_switch_checker: Callable[[], bool]):
        """
        Args:
            should_switch_checker: 检查是否应该切换等级的回调函数
        """
        self.adb = adb
        self.recognizer = recognizer
        self.state = state
        self._should_switch_to_higher_priority_level = should_switch_checker

    def start_battle(self, screenshot, match_info: Dict, needs_state_init: bool):
        """开始对战 - 先开启自动，再点击对战按钮

        Returns:
            bool: 是否需要返回上级
        """
        ocr_results = match_info.get("ocr_results", [])

        # 如果需要初始化状态且当前等级未设置，返回上级页面
        if needs_state_init and not self.state.get_current_level():
            print("  -> 需要初始化状态，返回上级页面")
            go_back(self.adb, self.recognizer, screenshot)
            return True

        # 检查是否应该切换到更高优先级的等级
        if self._should_switch_to_higher_priority_level():
            print("  -> 返回上级页面以选择更高优先级等级")
            go_back(self.adb, self.recognizer, screenshot)
            return True

        # 检查自动模式状态
        auto_box = None
        has_off = False
        auto_patterns = config.TEXT_PATTERNS.get("auto", [])

        for item in ocr_results:
            text = item['text'].strip()
            text_upper = text.upper()
            for pattern in auto_patterns:
                if pattern in text or pattern.upper() in text_upper:
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

        return False
