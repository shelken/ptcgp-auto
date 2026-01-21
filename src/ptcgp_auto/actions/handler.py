"""动作处理器 - 门面类"""

from typing import Dict

from ptcgp_auto import config
from ptcgp_auto.logger import get_logger

logger = get_logger(__name__)
from ptcgp_auto.adb_controller import AdbController
from ptcgp_auto.recognizer import Recognizer
from ptcgp_auto.state_manager import StateManager
from .base import BaseActions
from .battle import BattleActions
from .deck import DeckActions
from .expansion import ExpansionActions
from .home import HomeActions
from .level import LevelActions
from .pack import PackActions
from .tutorial import TutorialActions
from .user import UserActions


class ActionHandler:
    """动作处理器门面类，委托给各子模块"""

    def __init__(self, adb: AdbController, recognizer: Recognizer, state: StateManager):
        self.adb = adb
        self.recognizer = recognizer
        self.state = state
        # 状态变量
        self.current_pack_name = None  # 当前卡包名称（用于显示）
        self.current_pack_id = None  # 当前卡包 ID（左分母_右分母）
        self.tried_expansion_series = set()
        self.all_packs_checked = False
        self.needs_state_init = state.needs_initialization()
        # 子模块
        self._base = BaseActions(adb, recognizer)
        self._battle = BattleActions(
            adb, recognizer, state, self._should_switch_to_higher_priority_level
        )
        self._level = LevelActions(
            adb, recognizer, state, self._should_switch_to_higher_priority_level
        )
        self._deck = DeckActions(
            adb, recognizer, state, self._should_switch_to_higher_priority_level
        )
        self._expansion = ExpansionActions(
            adb, recognizer, state, self._should_switch_to_higher_priority_level
        )
        self._home = HomeActions(adb, recognizer, state)
        self._pack = PackActions(adb, recognizer, state)
        self._tutorial = TutorialActions(adb, recognizer)
        self._user = UserActions(adb, recognizer, state)

    # 需要跳过手指检测的动作（这些动作自己处理或不需要）
    _SKIP_HAND_CHECK_ACTIONS = {
        "click_identifier",
        "tap_screen_center",
        "click_continue_button",
        "click_cancel",
        "click_template",
        "wait",
        "wait_battle",
        "long_press_text",
        "handle_tutorial_unlock",
        "handle_tutorial_list",
        "handle_tutorial_step",
    }

    def execute(self, action: str, screenshot, match_info: Dict):
        """执行动作"""
        # 统一检测手指引导模板（新手教程），优先处理
        if action not in self._SKIP_HAND_CHECK_ACTIONS:
            hand_box = self.recognizer.find_template(
                screenshot, "hand_up_left", threshold=0.7
            )
            if hand_box:
                logger.info("  -> 检测到手指引导，点击")
                self.adb.tap_center(hand_box)
                return

        handler = getattr(self, f"action_{action}", None)
        if handler:
            handler(screenshot, match_info)
        else:
            logger.error(f"  -> 未知动作: {action}")

    # ==================== 基础动作（委托） ====================

    def action_click_identifier(self, screenshot, match_info: Dict):
        self._base.click_identifier(screenshot, match_info)

    def action_tap_screen_center(self, screenshot, match_info: Dict):
        self._base.tap_screen_center(screenshot, match_info)

    def action_click_continue_button(self, screenshot, match_info: Dict):
        self._base.click_continue_button(screenshot, match_info)

    def action_click_cancel(self, screenshot, match_info: Dict):
        self._base.click_cancel(screenshot, match_info)

    def action_click_auto_mode(self, screenshot, match_info: Dict):
        self._base.click_auto_mode(screenshot, match_info)

    def action_click_template(self, screenshot, match_info: Dict):
        self._base.click_template(screenshot, match_info)

    def action_wait(self, screenshot, match_info: Dict):
        self._base.wait(screenshot, match_info)

    def action_go_back(self, screenshot, match_info: Dict):
        """返回上一页"""
        from .utils import go_back

        go_back(self.adb, self.recognizer, screenshot)

    # ==================== 辅助方法 ====================

    def _should_switch_to_higher_priority_level(self) -> bool:
        """检查是否应该切换到更高优先级的等级"""
        current_level = self.state.get_current_level()
        if not current_level:
            return False

        for level in config.BATTLE_LEVELS:
            if not self.state.is_level_complete(level):
                if level != current_level:
                    logger.info(
                        f"  [优先级检查] 当前 {current_level}，但 {level} 未完成且优先级更高"
                    )
                    return True
                else:
                    return False
        return False

    # ==================== 对战动作（委托） ====================

    def action_start_battle(self, screenshot, match_info: Dict):
        self._battle.start_battle(screenshot, match_info, self.needs_state_init)

    def action_wait_battle(self, screenshot, match_info: Dict):
        self._battle.wait_battle(screenshot, match_info)

    # ==================== 等级选择动作（委托） ====================

    def action_select_level(self, screenshot, match_info: Dict):
        def on_init_complete():
            self.needs_state_init = False

        def reset_pack_state():
            self.all_packs_checked = False
            self.tried_expansion_series.clear()

        self._level.select_level(
            screenshot,
            match_info,
            self.needs_state_init,
            on_init_complete,
            reset_pack_state,
        )

    # ==================== 牌组列表动作（委托） ====================

    def action_handle_deck_list(self, screenshot, match_info: Dict):
        def set_all_packs_checked(val: bool):
            self.all_packs_checked = val

        def set_current_pack_name(name: str):
            self.current_pack_name = name

        self._deck.handle_deck_list(
            screenshot,
            match_info,
            self.needs_state_init,
            self.all_packs_checked,
            self.current_pack_id,
            self.current_pack_name,
            set_all_packs_checked,
            set_current_pack_name,
        )

    # ==================== 扩充组选择动作（委托） ====================

    def action_handle_expansion_select(self, screenshot, match_info: Dict):
        def set_tried_expansion_series(val: set):
            self.tried_expansion_series = val

        def set_all_packs_checked(val: bool):
            self.all_packs_checked = val

        def set_current_pack_id(val: str):
            self.current_pack_id = val

        self._expansion.handle_expansion_select(
            screenshot,
            match_info,
            self.tried_expansion_series,
            set_tried_expansion_series,
            set_all_packs_checked,
            set_current_pack_id,
        )

    # ==================== 主页动作（委托） ====================

    def action_find_incomplete(self, screenshot, match_info: Dict):
        self._home.find_incomplete(screenshot, match_info)

    def action_click_solo_battle(self, screenshot, match_info: Dict):
        self._home.click_solo_battle(screenshot, match_info)

    def action_handle_game_home(self, screenshot, match_info: Dict):
        self._home.handle_game_home(screenshot, match_info)

    # ==================== 开包动作（委托） ====================

    def set_target_pack(self, pack_code: str, booster_name: str):
        """设置目标卡包"""
        self._pack.set_target_pack(pack_code, booster_name)

    def action_click_pack_icon(self, screenshot, match_info: Dict):
        self._pack.click_pack_icon(screenshot, match_info)

    def action_select_pack_series(self, screenshot, match_info: Dict):
        self._pack.select_pack_series(screenshot, match_info)

    def action_select_pack(self, screenshot, match_info: Dict):
        self._pack.select_pack(screenshot, match_info)

    def action_click_open_pack(self, screenshot, match_info: Dict):
        self._pack.click_open_pack(screenshot, match_info)

    def action_handle_hourglass_popup(self, screenshot, match_info: Dict):
        self._pack.handle_hourglass_popup(screenshot, match_info)

    def action_swipe_open_pack(self, screenshot, match_info: Dict):
        self._pack.swipe_open_pack(screenshot, match_info)

    def action_long_press_text(self, screenshot, match_info: Dict):
        self._pack.long_press_text(screenshot, match_info)

    def action_long_press_center(self, screenshot, match_info: Dict):
        self._pack.long_press_center(screenshot, match_info)

    def action_swipe_up_card(self, screenshot, match_info: Dict):
        self._pack.swipe_up_card(screenshot, match_info)

    # ==================== 教程动作（委托） ====================

    def action_handle_tutorial_unlock(self, screenshot, match_info: Dict):
        self._tutorial.handle_tutorial_unlock(screenshot, match_info)

    def action_handle_tutorial_list(self, screenshot, match_info: Dict):
        self._tutorial.handle_tutorial_list(screenshot, match_info)

    def action_handle_tutorial_step(self, screenshot, match_info: Dict):
        self._tutorial.handle_tutorial_step(screenshot, match_info)

    # ==================== 用户信息动作（委托） ====================

    def action_extract_user_info(self, screenshot, match_info: Dict):
        self._user.extract_user_info(screenshot, match_info)

    def action_click_add_friends(self, screenshot, match_info: Dict):
        self._user.click_add_friends(screenshot, match_info)

    def action_click_friends_tab(self, screenshot, match_info: Dict):
        self._user.click_friends_tab(screenshot, match_info)
