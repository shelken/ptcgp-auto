"""动作处理器 - 门面类"""

from typing import Dict

from adb_controller import AdbController
from recognizer import Recognizer
from state_manager import StateManager


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

    def execute(self, action: str, screenshot, match_info: Dict):
        """执行动作"""
        handler = getattr(self, f"action_{action}", None)
        if handler:
            handler(screenshot, match_info)
        else:
            print(f"  -> 未知动作: {action}")
