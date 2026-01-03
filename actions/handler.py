"""动作处理器 - 门面类"""

from typing import Dict

import config
from adb_controller import AdbController
from recognizer import Recognizer
from state_manager import StateManager
from .base import BaseActions
from .battle import BattleActions


class ActionHandler:
    """动作处理器门面类，委托给各子模块"""

    def __init__(
        self,
        adb: AdbController,
        recognizer: Recognizer,
        state: StateManager
    ):
        self.adb = adb
        self.recognizer = recognizer
        self.state = state
        # 状态变量
        self.current_pack_name = None
        self.current_pack_total = None
        self.tried_expansion_series = set()
        self.all_packs_checked = False
        self.needs_state_init = state.needs_initialization()
        # 子模块
        self._base = BaseActions(adb, recognizer)
        self._battle = BattleActions(
            adb, recognizer, state,
            self._should_switch_to_higher_priority_level
        )

    def execute(self, action: str, screenshot, match_info: Dict):
        """执行动作"""
        handler = getattr(self, f"action_{action}", None)
        if handler:
            handler(screenshot, match_info)
        else:
            print(f"  -> 未知动作: {action}")

    # ==================== 基础动作（委托） ====================

    def action_click_identifier(self, screenshot, match_info: Dict):
        self._base.click_identifier(screenshot, match_info)

    def action_click_continue(self, screenshot, match_info: Dict):
        self._base.click_continue(screenshot, match_info)

    def action_click_cancel(self, screenshot, match_info: Dict):
        self._base.click_cancel(screenshot, match_info)

    def action_click_template(self, screenshot, match_info: Dict):
        self._base.click_template(screenshot, match_info)

    def action_wait(self, screenshot, match_info: Dict):
        self._base.wait(screenshot, match_info)

    # ==================== 辅助方法 ====================

    def _should_switch_to_higher_priority_level(self) -> bool:
        """检查是否应该切换到更高优先级的等级"""
        current_level = self.state.get_current_level()
        if not current_level:
            return False

        for level in config.BATTLE_LEVELS:
            if not self.state.is_level_complete(level):
                if level != current_level:
                    print(f"  [优先级检查] 当前 {current_level}，但 {level} 未完成且优先级更高")
                    return True
                else:
                    return False
        return False

    # ==================== 对战动作（委托） ====================

    def action_start_battle(self, screenshot, match_info: Dict):
        self._battle.start_battle(screenshot, match_info, self.needs_state_init)
