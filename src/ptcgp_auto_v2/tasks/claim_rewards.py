# -*- coding: utf-8 -*-
"""
任务奖励领取任务模块

优化后的流程：主页检测奖励图标 → 进入任务页面 → 领取当前Tab所有奖励 →
进入主题收藏领取 → 返回Tab页面 → 直接返回主页 → 重新检测
"""

import logging
import time

from ptcgp_auto_v2.core.task_base import (
    ActionResult,
    ResetType,
    Task,
    TaskRegistry,
    TaskResult,
)
from ptcgp_auto_v2.locales import get_text_patterns
from ptcgp_auto_v2.tasks.utils.pack_opening_flow import swipe_card_register
from ptcgp_auto_v2.utils.color import is_button_clickable
from ptcgp_auto_v2.utils.gesture import (
    click_close,
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


def _build_rewards_page_tabs_patterns() -> list[str]:
    """动态构建 rewards_page 的 Tab 栏识别文本

    包含所有任务页面的 Tab 文本模式。
    """
    # 所有可能的 Tab 类型
    tabs = [
        "daily",
        "collection",
        "deck",
        "drop",
        "account_link",
        "elite_deck",
        "convenient_cards",
        "reward_week",
        "medal",
        "premium",
    ]
    patterns = []
    for tab in tabs:
        patterns.extend(get_text_patterns(f"rewards_tab_{tab}"))
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
        # 每日 / 圖鑑 / 牌組 / 掉落 / 帳號連結 / 特級 / 精英牌組 / 便利卡牌 / 獎勵週 / 勳章
        {
            "name": "rewards_page",
            "identifiers": _build_rewards_page_tabs_patterns(),
            "exact_match": True,
            "priority": 15,
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
class ClaimRewardsTask(Task):
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
    max_iterations = 100
    screenshot_lossless = True
    pages = _build_claim_rewards_pages()

    def __init__(self, adb, recognizer, page_detector):
        super().__init__(adb, recognizer, page_detector)

        # 页面内操作缓存
        self._action_cache: dict[str, bool] = {}

        # 任务状态
        self._home_check_count = 0  # 主页无奖励检查次数
        self._completed = False  # 任务完成标志

    def _is_action_done(self, key: str) -> bool:
        """检查操作是否已完成"""
        return self._action_cache.get(key, False)

    def _mark_action_done(self, key: str):
        """标记操作已完成"""
        self._action_cache[key] = True

    def _reset_action_cache(self):
        """重置操作缓存"""
        self._action_cache.clear()

    def on_start(self):
        """任务开始前的初始化"""
        logger.info("任务奖励领取任务开始")
        self._reset_action_cache()
        self._home_check_count = 0
        self._completed = False

    def is_completed(self) -> bool:
        """判断任务是否已完成"""
        return self._completed

    def handle_page(self, page_name: str, page_info: dict) -> ActionResult:
        """处理识别到的页面"""
        logger.debug(f"处理页面: {page_name}")

        # 页面处理器映射
        handlers = {
            "game_home_main": self._handle_home,
            "rewards_page": self._handle_rewards_page,
            "reward_detail_page": self._handle_reward_detail,
            "theme_collection_page": self._handle_theme_collection,
            "pack_card_register": self._handle_card_register,
            "speed_up_button": self._handle_speed_up,
        }

        handler = handlers.get(page_name)
        if handler:
            return handler(page_info)

        logger.warning(f"未处理的页面: {page_name}")
        return ActionResult.ok(wait=1.0)

    def _handle_speed_up(self, page_info: dict) -> ActionResult:
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
            f"任务完成，主页检测次数: {self._home_check_count}, "
            f"结果: {'成功' if result.success else '失败'}"
        )

    # ============================================================
    # 页面处理方法
    # ============================================================

    def _handle_home(self, page_info: dict) -> ActionResult:
        """处理主页：检测是否有奖励图标"""
        self._reset_action_cache()

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
                self._home_check_count = 0  # 重置检测计数器
                return tap_box(self.adb, reward_icon.box, wait=3.0)

            logger.debug(f"  -> 未检测到奖励图标 ({i + 1}/{rounds})")
            if i < rounds - 1:
                time.sleep(interval)

        # 多次检查无奖励，累计检查次数
        self._home_check_count += 1
        logger.debug(f"  -> 确认无奖励图标（第 {self._home_check_count} 轮检查）")

        if self._home_check_count >= rounds:
            logger.debug("  -> 确认无奖励，任务完成")
            self._completed = True

        return ActionResult.ok(wait=1.0)

    def _handle_rewards_page(self, page_info: dict) -> ActionResult:
        """处理任务奖励页面：领取当前 Tab 所有奖励，然后处理主题收藏，最后返回主页

        优化逻辑：如果 Tab 页面领取过奖励，跳过主题收藏直接返回主页
        """
        screenshot, ocr_results = self.page_detector.get_last_page_context()

        # 1. 尝试点击领取按钮
        result = self._try_claim_buttons(ocr_results, screenshot)
        if result:
            # 成功领取，标记 Tab 页面已领取过奖励
            self._mark_action_done("tab_claimed")
            return result

        # 2. 当前 Tab 无可领取，判断是否进入主题收藏
        # 如果 Tab 页面领取过奖励，直接返回主页（跳过主题收藏）
        if self._is_action_done("tab_claimed"):
            logger.debug("  -> Tab 页面已领取过奖励，跳过主题收藏，直接返回主页")
            close_patterns = get_text_patterns("close_button")
            result = click_close(
                self.adb, self.page_detector, ocr_results, close_patterns
            )
            if result:
                return result
            back_patterns = get_text_patterns("back_button")
            return navigate_back(
                self.adb, self.page_detector, ocr_results, back_patterns
            )

        # 3. Tab 页面没有领取过奖励，需要检查主题收藏
        if not self._is_action_done("theme_checked"):
            theme_patterns = get_text_patterns("theme_collection")
            result = tap_text(self.adb, ocr_results, theme_patterns, wait=2.0)
            if result:
                logger.debug("  -> Tab 页面无奖励，进入主题收藏检查")
                self._mark_action_done("theme_checked")
                return result
            else:
                logger.debug("  -> 未找到主题收藏入口，跳过")
                self._mark_action_done("theme_checked")

        # 4. 已检查主题收藏（或没有入口），返回主页
        logger.debug("  -> 当前 Tab 和主题收藏都已处理，返回主页")
        close_patterns = get_text_patterns("close_button")
        result = click_close(self.adb, self.page_detector, ocr_results, close_patterns)
        if result:
            return result
        back_patterns = get_text_patterns("back_button")
        return navigate_back(self.adb, self.page_detector, ocr_results, back_patterns)

    def _try_claim_buttons(
        self, ocr_results: list[dict], screenshot
    ) -> ActionResult | None:
        """尝试点击可领取的按钮（全部領取/領取/達成）

        注意：只有"全部領取"按钮需要颜色检查（避免点击置灰按钮），
        其他按钮（領取/達成）直接点击，不需要颜色检查。
        """
        claim_patterns = get_text_patterns("reward_claim_buttons")
        # 需要颜色检查的模式（全部領取的多语言版本）
        color_check_patterns = get_text_patterns("reward_claim_all")

        wait = 1.2
        for pattern in claim_patterns:
            for item in ocr_results:
                text = "".join(item["text"].lower().split())
                if "".join(pattern.lower().split()) == text:
                    box = item["box"]

                    # 检查是否是"全部領取"，需要进行颜色检查
                    normalized_pattern = "".join(pattern.lower().split())
                    is_claim_all = any(
                        normalized_pattern == "".join(cp.lower().split())
                        for cp in color_check_patterns
                    )

                    if is_claim_all:
                        # 全部領取需要颜色检查
                        if screenshot and is_button_clickable(
                            screenshot, box, threshold=0.3
                        ):
                            logger.info(f"  -> 点击全部领取按钮: {pattern}")
                            return tap_box(self.adb, box, wait=wait)
                        else:
                            logger.debug(f"  -> 全部领取按钮 {pattern} 已置灰，跳过")
                    else:
                        # 其他按钮（領取/達成）直接点击，不需要颜色检查
                        logger.info(f"  -> 点击领取按钮: {pattern}")
                        return tap_box(self.adb, box, wait=wait)

        return None

    def _handle_theme_collection(self, page_info: dict) -> ActionResult:
        """处理主题收藏页面：领取所有奖励后返回 Tab 页面"""
        screenshot, ocr_results = self.page_detector.get_last_page_context()

        result = self._try_claim_buttons(ocr_results, screenshot)
        if result:
            return result

        # 无可领取，返回 Tab 页面
        logger.debug("  -> 主题收藏领取完成，返回 Tab 页面")
        back_patterns = get_text_patterns("back_button")
        return navigate_back(self.adb, self.page_detector, ocr_results, back_patterns)

    def _handle_card_register(self, page_info: dict) -> ActionResult:
        """向上滑动卡牌登录图鉴（精英牌组奖励）"""
        return swipe_card_register(self.adb)

    def _handle_reward_detail(self, page_info: dict) -> ActionResult:
        """处理奖励详情页面：点击達成按钮"""
        screenshot, ocr_results = self.page_detector.get_last_page_context()

        result = self._try_claim_buttons(ocr_results, screenshot)
        if result:
            return result

        logger.debug("  -> 奖励详情页面，等待...")
        return ActionResult.ok(wait=1.0)
