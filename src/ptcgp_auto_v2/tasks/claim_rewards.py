# -*- coding: utf-8 -*-
"""
任务奖励领取任务模块

优化后的流程：主页检测奖励图标 → 进入任务页面 → 领取当前Tab所有奖励 →
进入主题收藏领取 → 返回Tab页面 → 直接返回主页 → 重新检测
"""

import logging
import time

from ptcgp_auto_v2.core.stateful_task import StatefulTask
from ptcgp_auto_v2.core.task_base import (
    ActionResult,
    ResetType,
    TaskRegistry,
    TaskResult,
)
from ptcgp_auto_v2.infra.adb import ScreenshotMode
from ptcgp_auto_v2.locales import get_locale_module, get_text_patterns
from ptcgp_auto_v2.tasks.utils.pack_opening_flow import swipe_card_register
from ptcgp_auto_v2.utils.color import is_button_clickable
from ptcgp_auto_v2.utils.gesture import (
    click_close,
    find_text_matches,
    navigate_back,
    quick_tap,
    tap_box,
    tap_matched_element,
    tap_text,
)

logger = logging.getLogger(__name__)

# ============================================================
# 常量定义
# ============================================================

# 主页检查轮数（连续多少次检测无奖励后确认完成）
HOME_CHECK_ROUNDS = 2

# 主页检查间隔 (s)
HOME_CHECK_INTERVAL = 2.0


# ============================================================
# 页面识别规则
# ============================================================


PERMANENT_REWARDS_TAB_KEYS = {
    "rewards_tab_daily",
    "rewards_tab_collection",
    "rewards_tab_deck",
    "rewards_tab_drop",
    "rewards_tab_account_link",
    "rewards_tab_premium",
    "rewards_tab_elite_deck",
    "rewards_tab_convenient_cards",
    "rewards_tab_medal",
}


def _get_rewards_tab_keys() -> list[str]:
    """获取所有奖励页 Tab 文本 key"""
    patterns_dict = getattr(get_locale_module(), "TEXT_PATTERNS", {})
    return [key for key in patterns_dict if key.startswith("rewards_tab_")]


def _build_rewards_page_tabs_patterns(exact_match: bool | None = None) -> list[str]:
    """动态构建 rewards_page 的 Tab 栏识别文本"""
    patterns = []
    for key in _get_rewards_tab_keys():
        is_exact_key = key in PERMANENT_REWARDS_TAB_KEYS
        if exact_match is not None and exact_match != is_exact_key:
            continue
        patterns.extend(get_text_patterns(key))
    return patterns


def _build_claim_rewards_pages() -> list[dict]:
    """构建任务奖励领取页面规则"""
    return [
        # 商店 / 得卡挑戰
        {
            "name": "game_home_main",
            "match_all": True,
            "identifiers": get_text_patterns("game_home_main"),
            "priority": 10,
        },
        # 常驻 Tab 精确匹配，避免误伤其他页面
        {
            "name": "rewards_page",
            "identifiers": _build_rewards_page_tabs_patterns(exact_match=True),
            "exact_match": True,
            "priority": 15,
            "exclude_identifiers": get_text_patterns("rewards_page_exclude"),
        },
        # 限时任务 Tab 模糊匹配，兼容活动名带图标或额外文案
        {
            "name": "rewards_page",
            "identifiers": _build_rewards_page_tabs_patterns(exact_match=False),
            "priority": 14,
            "exclude_identifiers": get_text_patterns("rewards_page_exclude"),
        },
        # 報酬 / 達成！
        {
            "name": "reward_detail_page",
            "identifiers": get_text_patterns("reward_detail_page"),
            "match_all": True,
            "priority": 16,
        },
        # 主題收藏
        {
            "name": "theme_collection_page",
            "identifiers": get_text_patterns("theme_collection"),
            "exclude_identifiers": _build_rewards_page_tabs_patterns(),
            "priority": 20,
        },
        # 快进按钮
        {"name": "speed_up_button", "templates": ["btn_speed_up"], "priority": 23},
        # 向上輕滑卡牌
        {
            "name": "pack_card_register",
            "identifiers": get_text_patterns("pack_card_register"),
            "priority": 25,
        },
    ]


@TaskRegistry.register("claim_rewards")
class ClaimRewardsTask(StatefulTask):
    """
    任务奖励领取任务（优化版）

    自动领取游戏中的所有任务奖励，采用简化流程：
    1. 主页检测奖励图标，点击进入
    2. 游戏自动跳转到有奖励的 Tab，领取该页面所有奖励
    3. 进入主题收藏领取奖励
    4. 返回 Tab 页面，再返回主页
    5. 主页重新检测，连续 2 轮无奖励则完成
    """

    task_type = "claim_rewards"
    reset_type = ResetType.DAILY
    max_iterations = 150
    screenshot_ocr_mode = ScreenshotMode.DISPLAY_RAW
    max_same_page_rounds = 25
    pages = _build_claim_rewards_pages()

    def __init__(self, adb, recognizer, page_detector):
        super().__init__(adb, recognizer, page_detector)

    def on_start(self):
        """任务开始前的初始化"""
        logger.info("任务奖励领取任务开始")
        self.state.reset()
        self.state_set("home_check_count", 0)
        self.state_set("returned_from_theme_collection", False)
        self.state_set("claimed_current_rewards_tab", False)
        self.state_set("should_try_theme_collection", False)
        self.state_set("theme_collection_attempted", False)

    def handle_unmapped_page(self, page_name: str, page_info: dict) -> ActionResult:
        logger.debug(f"处理页面: {page_name}")
        logger.warning(f"未处理的页面: {page_name}")
        return ActionResult.ok(wait=1.0)

    def _handle_speed_up_button(self, page_info: dict) -> ActionResult:
        """处理快进按钮"""
        return tap_matched_element(self.adb, page_info, 0.3) or ActionResult.ok(
            wait=0.3
        )

    def handle_unknown_page(self, page_info) -> ActionResult:
        """处理未知页面"""
        logger.debug("未知页面，点击屏幕上方兜底")
        return quick_tap(self.adb, self.adb.center_x(), self.adb.scaled_y(10))

    def on_complete(self, result: TaskResult):
        """任务完成后的处理"""
        logger.info(
            f"任务完成，主页检测次数: {int(self.state_get('home_check_count', 0))}, "
            f"结果: {'成功' if result.success else '失败'}"
        )

    # ============================================================
    # 页面处理方法
    # ============================================================

    def _handle_game_home_main(self, page_info: dict) -> ActionResult:
        """处理主页：检测是否有奖励图标"""
        self.reset_action_cache()

        rounds = HOME_CHECK_ROUNDS
        interval = HOME_CHECK_INTERVAL

        # 连续检测，间隔固定秒数
        for i in range(rounds):
            screenshot, _ = self.page_detector.capture()
            if not screenshot:
                logger.warning("  -> 无法获取截图")
                time.sleep(interval)
                continue

            # 检测 icon_has_reward 模板
            reward_icon = self.page_detector.find_template_with_scale(
                "icon_has_reward", screenshot=screenshot
            )

            if reward_icon:
                logger.debug("  -> 检测到奖励图标，进入任务页面")
                self.state_set("home_check_count", 0)
                should_try_theme = bool(
                    self.state_get("should_try_theme_collection", False)
                )
                theme_already_attempted = bool(
                    self.state_get("theme_collection_attempted", False)
                )
                self.state_set("claimed_current_rewards_tab", False)
                if not should_try_theme or theme_already_attempted:
                    self.state_set("returned_from_theme_collection", False)
                    self.state_set("should_try_theme_collection", False)
                return tap_box(self.adb, reward_icon.box, wait=3.0)

            logger.debug(f"  -> 未检测到奖励图标 ({i + 1}/{rounds})")
            if i < rounds - 1:
                time.sleep(interval)

        # 多次检查无奖励，累计检查次数
        home_check_count = int(self.state_get("home_check_count", 0)) + 1
        self.state_set("home_check_count", home_check_count)
        logger.debug(f"  -> 确认无奖励图标（第 {home_check_count} 轮检查）")

        if home_check_count >= rounds:
            logger.debug("  -> 确认无奖励，任务完成")
            self.complete()

        return ActionResult.ok(wait=1.0)

    def _handle_rewards_page(self, page_info: dict) -> ActionResult:
        """奖励页只做三件事：收尾返回、领取、按需进主题收藏。"""
        screenshot, ocr_results = self.page_detector.get_last_page_context()

        if bool(self.state_get("returned_from_theme_collection", False)):
            logger.debug("  -> 已从主题收藏返回，关闭任务页")
            self.state_set("returned_from_theme_collection", False)
            self.state_set("claimed_current_rewards_tab", False)
            self.state_set("should_try_theme_collection", False)
            return self._leave_rewards_page(ocr_results)

        if not bool(self.state_get("claimed_current_rewards_tab", False)):
            if self._click_claim_buttons(ocr_results, screenshot):
                self.state_set("claimed_current_rewards_tab", True)
                logger.debug("  -> 当前 Tab 已点击领取，等待奖励弹窗收敛")
                return ActionResult.ok(wait=1.8)

        if bool(self.state_get("should_try_theme_collection", False)):
            if bool(self.state_get("theme_collection_attempted", False)):
                logger.debug("  -> 主题收藏已尝试过，关闭任务页")
                self.state_set("should_try_theme_collection", False)
                self.state_set("claimed_current_rewards_tab", False)
                return self._leave_rewards_page(ocr_results)

            if self._needs_theme_collection(ocr_results, screenshot):
                result = tap_text(
                    self.adb,
                    ocr_results,
                    get_text_patterns("theme_collection"),
                    wait=2.0,
                    exact=True,
                )
                if result:
                    logger.debug("  -> 进入主题收藏")
                    return result
                logger.debug("  -> 未找到主题收藏入口，关闭任务页")
                return self._leave_rewards_page(ocr_results)
            logger.debug("  -> 无需主题收藏，关闭任务页")
            self.state_set("should_try_theme_collection", False)
            return self._leave_rewards_page(ocr_results)

        if bool(self.state_get("claimed_current_rewards_tab", False)):
            logger.debug("  -> 当前 Tab 已处理，回主页确认是否还有奖励")
            self.state_set("should_try_theme_collection", True)
            return self._leave_rewards_page(ocr_results)

        if not bool(self.state_get("theme_collection_attempted", False)):
            if self._needs_theme_collection(ocr_results, screenshot):
                result = tap_text(
                    self.adb,
                    ocr_results,
                    get_text_patterns("theme_collection"),
                    wait=2.0,
                    exact=True,
                )
                if result:
                    logger.debug("  -> 进入主题收藏")
                    return result
                logger.debug("  -> 未找到主题收藏入口，关闭任务页")
                return self._leave_rewards_page(ocr_results)

        logger.debug("  -> 当前 Tab 已处理，关闭任务页")
        return self._leave_rewards_page(ocr_results)

    def _handle_theme_collection_page(self, page_info: dict) -> ActionResult:
        """主题收藏页领取后返回任务页，由任务页统一关闭。"""
        screenshot, ocr_results = self.page_detector.get_last_page_context()

        if bool(self.state_get("theme_collection_attempted", False)):
            logger.debug("  -> 主题收藏已尝试过，直接返回任务页")
            self.state_set("returned_from_theme_collection", True)
            return navigate_back(self.adb, self.page_detector, ocr_results)

        if self._click_claim_buttons(ocr_results, screenshot):
            return ActionResult.ok(wait=1.8)

        logger.debug("  -> 主题收藏已处理，返回任务页")
        self.state_set("theme_collection_attempted", True)
        self.state_set("returned_from_theme_collection", True)
        return navigate_back(self.adb, self.page_detector, ocr_results)

    def _click_claim_buttons(self, ocr_results: list[dict], screenshot) -> bool:
        """先点全部领取，再点单个领取；返回本轮是否点过领取按钮。"""
        clicked = False
        claim_all_patterns = get_text_patterns("reward_claim_all")
        claim_all_matches = find_text_matches(
            ocr_results,
            claim_all_patterns,
            exact=True,
        )
        if claim_all_matches:
            logger.info("  -> 点击全部领取按钮")
            clicked = bool(
                tap_text(
                    self.adb,
                    ocr_results,
                    claim_all_patterns,
                    wait=0.0,
                    exact=True,
                )
            )

        single_result = tap_text(
            self.adb,
            ocr_results,
            self._single_claim_patterns(),
            wait=0.0,
            exact=True,
        )
        return bool(single_result) or clicked

    def _needs_theme_collection(self, ocr_results: list[dict], screenshot) -> bool:
        """全部领取置灰，或没有任何领取入口时，才检查主题收藏。"""
        claim_all_matches = find_text_matches(
            ocr_results,
            get_text_patterns("reward_claim_all"),
            exact=True,
        )
        if claim_all_matches:
            return not self._is_claim_all_clickable(
                claim_all_matches[0]["box"],
                screenshot,
            )

        single_matches = find_text_matches(
            ocr_results,
            self._single_claim_patterns(),
            exact=True,
        )
        return not bool(single_matches)

    def _leave_rewards_page(self, ocr_results: list[dict]) -> ActionResult:
        """关闭任务页，模板失败时走返回。"""
        result = click_close(
            self.adb,
            self.page_detector,
            ocr_results,
            get_text_patterns("close_button"),
        )
        if result:
            return result
        return navigate_back(self.adb, self.page_detector, ocr_results)

    @staticmethod
    def _single_claim_patterns() -> list[str]:
        """除全部领取之外的奖励领取按钮。"""
        claim_all_patterns = set(get_text_patterns("reward_claim_all"))
        return [
            pattern
            for pattern in get_text_patterns("reward_claim_buttons")
            if pattern not in claim_all_patterns
        ]

    @staticmethod
    def _is_claim_all_clickable(box: tuple[int, int, int, int], screenshot) -> bool:
        """全部领取是否为绿色可点击状态。"""
        return bool(screenshot and is_button_clickable(screenshot, box, threshold=0.3))

    def _handle_pack_card_register(self, page_info: dict) -> ActionResult:
        """向上滑动卡牌登录图鉴（精英牌组奖励）"""
        return swipe_card_register(self.adb)

    def _handle_reward_detail_page(self, page_info: dict) -> ActionResult:
        """处理奖励详情页面：点击達成按钮"""
        screenshot, ocr_results = self.page_detector.get_last_page_context()

        if self._click_claim_buttons(ocr_results, screenshot):
            return ActionResult.ok(wait=1.8)

        logger.debug("  -> 奖励详情页面，等待...")
        return ActionResult.ok(wait=1.0)
