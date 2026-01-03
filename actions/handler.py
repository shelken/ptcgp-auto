"""动作处理器 - 门面类"""

from typing import Dict

from adb_controller import AdbController
from recognizer import Recognizer
from state_manager import StateManager
from .base import BaseActions


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
