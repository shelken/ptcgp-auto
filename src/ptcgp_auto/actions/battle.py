"""对战相关动作模块"""

import time
from typing import Dict, Callable

from ptcgp_auto import config
from ptcgp_auto.logger import get_logger
from .utils import find_auto_mode_button, find_text_by_variants, go_back

logger = get_logger(__name__)


class BattleActions:
    """对战相关动作处理"""

    def __init__(
        self, adb, recognizer, state, should_switch_checker: Callable[[], bool]
    ):
        """
        Args:
            should_switch_checker: 检查是否应该切换等级的回调函数
        """
        self.adb = adb
        self.recognizer = recognizer
        self.state = state
        self._should_switch_to_higher_priority_level = should_switch_checker
        self.battle_started_notified = False

    def start_battle(self, screenshot, match_info: Dict, needs_state_init: bool):
        """开始对战 - 先开启自动，再点击对战按钮

        Returns:
            bool: 是否需要返回上级
        """
        ocr_results = match_info.get("ocr_results", [])

        # 检查是否有"首次過關報酬"，没有说明被弹窗遮挡
        reward_item = find_text_by_variants(ocr_results, "first_clear_reward")
        if not reward_item:
            # 尝试点击关闭按钮
            close_box = self.recognizer.find_template(screenshot, "btn_close")
            if close_box:
                logger.info("  -> 检测到弹窗遮挡，点击关闭")
                self.adb.tap_center(close_box)
                return False
            # 没有关闭按钮，点击屏幕中央关闭弹窗
            logger.info("  -> 检测到弹窗遮挡，点击屏幕继续")
            self.adb.tap(config.SCREEN_WIDTH // 2, config.SCREEN_HEIGHT // 2)
            return False

        # 如果需要初始化状态且当前等级未设置，返回上级页面
        if needs_state_init and not self.state.get_current_level():
            logger.info("  -> 需要初始化状态，返回上级页面")
            go_back(self.adb, self.recognizer, screenshot)
            return True

        # 检查是否应该切换到更高优先级的等级
        if self._should_switch_to_higher_priority_level():
            logger.info("  -> 返回上级页面以选择更高优先级等级")
            go_back(self.adb, self.recognizer, screenshot)
            return True

        # 检查自动模式状态
        result = find_auto_mode_button(ocr_results)
        if result:
            auto_item, has_off = result
            # 如果自动模式是 OFF，先点击开启
            if has_off:
                logger.info("  -> 开启自动模式")
                self.adb.tap_center(auto_item["box"])
                time.sleep(0.5)

        # 点击对战按钮
        battle_box = match_info.get("box")
        if battle_box:
            # 首次进入对战时发送通知
            if not self.battle_started_notified:
                if config.NOTIFICATION_ENABLED:
                    from ptcgp_auto.notifier import notify_battle_started

                    level = self.state.get_current_level() or "未知"
                    username = None
                    if self.state.has_user_info():
                        username = self.state.get_user_info().get("username")
                    notify_battle_started(
                        config.NOTIFICATION_WEBHOOK_KEY,
                        level,
                        config.NOTIFICATION_SOUND,
                        port=config.ADB_PORT,
                        username=username,
                    )
                self.battle_started_notified = True

            logger.info("  -> 点击对战")
            self.adb.tap_center(battle_box)

        return False

    def wait_battle(self, screenshot, match_info: Dict):
        """对战中等待 - 检测并开启自动对战"""
        # 根据配置决定是否检测自动对战
        if config.AUTO_ENABLE_AUTO_BATTLE:
            auto_enabled = self.recognizer.check_state(screenshot, "auto_battle")

            if auto_enabled is False:
                # 自动对战未开启，点击开启
                logger.info("  -> 开启自动对战")
                auto_box = self.recognizer.find_text_variants(screenshot, "auto")
                if auto_box:
                    self.adb.tap_center(auto_box)
                    time.sleep(0.5)
                    return  # 开启后立即返回，下次循环继续检测

        logger.info("  -> 对战中，等待...")
        time.sleep(config.WAIT_BATTLE_CHECK_INTERVAL)
