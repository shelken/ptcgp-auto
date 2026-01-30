# -*- coding: utf-8 -*-
"""
任务奖励领取任务模块

采用字典映射处理页面，使用 action_cache 管理页面内操作状态。
流程：主页检测奖励图标 → 进入任务奖励页面 → 遍历 Tab 领取 → 主题收藏 → 返回主页检查
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
from ptcgp_auto_v2.utils.color import is_button_clickable
from ptcgp_auto_v2.utils.gesture import (
    click_close,
    is_text_visible,
    navigate_back,
    tap_box,
    tap_home_icon,
    tap_text,
)

logger = logging.getLogger(__name__)

# ============================================================
# 常量定义
# ============================================================

# 最大领取轮数
MAX_ROUNDS = 3

# 主页检查轮数
HOME_CHECK_ROUNDS = 2

# 主页检查间隔 (s)
HOME_CHECK_INTERVAL = 2.0

# Tab 遍历顺序
FIXED_TABS = ["daily", "collection", "deck"]
DYNAMIC_TABS = ["drop"]
WALL_TAB = "premium"
TAB_ORDER = FIXED_TABS + DYNAMIC_TABS + [WALL_TAB]


# ============================================================
# 页面识别规则
# ============================================================


def _build_claim_rewards_pages() -> list[dict]:
    """构建任务奖励领取页面规则"""
    return [
        {
            # 游戏主页：检测是否有奖励图标的起点
            "name": "game_home_main",
            "match_all": True,
            "identifiers": get_text_patterns("game_home_main"),
            "priority": 10,
        },
        {
            # 任务奖励页面：底部有 Tab 栏
            "name": "rewards_page",
            "identifiers": get_text_patterns("rewards_page_tabs"),
            "exact_match": True,
            "priority": 15,
        },
        {
            # 奖励详情页面
            "name": "reward_detail_page",
            "identifiers": get_text_patterns("reward_detail_page"),
            "match_all": True,
            "priority": 16,
        },
        {
            # 主题收藏页面
            "name": "theme_collection_page",
            "identifiers": get_text_patterns("theme_collection"),
            "priority": 20,
        },
        {
            # 通用 home_icon
            "name": "home_icon",
            "templates": ["icon_home"],
            "priority": 50,
        },
    ]


@TaskRegistry.register("claim_rewards")
class ClaimRewardsTask(Task):
    """
    任务奖励领取任务

    自动领取游戏中的所有任务奖励，包括每日任务、图鉴任务、牌组任务、掉落活动奖励、主题收藏奖励。
    """

    task_type = "claim_rewards"
    reset_type = ResetType.DAILY
    max_iterations = 150
    max_unknown_pages = 15
    pages = _build_claim_rewards_pages()

    def __init__(self, adb, recognizer, page_detector):
        super().__init__(adb, recognizer, page_detector)

        # 页面内操作缓存
        self._action_cache: dict[str, bool] = {}

        # 任务状态
        self._home_check_count = 0  # 主页无奖励检查次数
        self._round_count = 0  # 当前领取轮数
        self._completed = False  # 任务完成标志

        # Tab 遍历状态（使用缓存键记录）
        self._visited_tabs: set[str] = set()
        self._theme_collection_done = False
        self._going_left = True

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
        self._round_count = 0
        self._completed = False
        self._reset_tab_state()

    def _reset_tab_state(self):
        """重置 Tab 遍历状态（用于下一轮）"""
        self._visited_tabs.clear()
        self._theme_collection_done = False
        self._going_left = True

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
            "home_icon": self._handle_home_icon,
        }

        handler = handlers.get(page_name)
        if handler:
            return handler(page_info)

        logger.warning(f"未处理的页面: {page_name}")
        return ActionResult.ok(wait=1.0)

    def on_complete(self, result: TaskResult):
        """任务完成后的处理"""
        logger.info(
            f"任务完成，轮数: {self._round_count}, "
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
                self._home_check_count = 0
                return tap_box(self.adb, reward_icon.box, wait=3.0)

            logger.debug(f"  -> 未检测到奖励图标 ({i + 1}/{rounds})")
            if i < rounds - 1:
                time.sleep(interval)

        # 多次检查无奖励，累计检查次数
        self._home_check_count += 1
        logger.debug(f"  -> 确认无奖励图标（第 {self._home_check_count} 轮检查）")

        if self._home_check_count >= rounds or self._round_count >= MAX_ROUNDS:
            logger.debug("  -> 确认无奖励，任务完成")
            self._completed = True

        return ActionResult.ok(wait=1.0)

    def _handle_rewards_page(self, page_info: dict) -> ActionResult:
        """处理任务奖励页面：遍历 Tab 领取奖励"""
        screenshot, ocr_results = self.page_detector.get_last_page_context()

        # 1. 尝试点击领取按钮
        result = self._try_claim_buttons(ocr_results, screenshot)
        if result:
            return result

        # 2. 当前 Tab 无可领取，切换 Tab
        tab_patterns_map = {
            tab: get_text_patterns(f"rewards_tab_{tab}") for tab in TAB_ORDER
        }

        def is_visible(tab: str) -> bool:
            patterns = tab_patterns_map.get(tab, [])
            if not patterns:
                return False
            return is_text_visible(ocr_results, patterns, exact=True)

        def tap_tab(tab: str) -> ActionResult | None:
            patterns = tab_patterns_map.get(tab, [])
            if not patterns:
                return None
            return tap_text(self.adb, ocr_results, patterns, wait=1.0, exact=True)

        first_tab = TAB_ORDER[0]
        first_tab_visible = is_visible(first_tab)

        # 阶段1：往左走，直到"每日"可见
        if self._going_left:
            if first_tab_visible:
                self._going_left = False
            else:
                for tab in TAB_ORDER:
                    result = tap_tab(tab)
                    if result:
                        logger.debug(f"  -> 往左走，点击 {tab} Tab")
                        return result

        # 阶段2：往右走，从左往右依次点击未访问的 Tab
        if not self._going_left:
            wall_visible = is_visible(WALL_TAB)

            for tab in TAB_ORDER:
                if tab == WALL_TAB:
                    break

                if tab in self._visited_tabs:
                    continue

                if is_visible(tab):
                    result = tap_tab(tab)
                    if result:
                        logger.debug(f"  -> 点击 {tab} Tab")
                        self._visited_tabs.add(tab)
                        return result
                else:
                    if wall_visible:
                        logger.debug(
                            f"  -> 已达最右 (看到 {WALL_TAB}) 但未见 {tab}，跳过"
                        )
                        self._visited_tabs.add(tab)
                        continue

                    # 尝试点击最右侧可见 Tab 以继续往右
                    found_nav_tab = False
                    for right_tab in reversed(TAB_ORDER):
                        if right_tab == WALL_TAB:
                            continue
                        if is_visible(right_tab):
                            # 如果最右侧可见 Tab 已经访问过，说明已到达最右
                            if right_tab in self._visited_tabs:
                                logger.debug(
                                    f"  -> 已到达最右 (已访问 {right_tab}) 但未见 {tab}，跳过"
                                )
                                self._visited_tabs.add(tab)
                                found_nav_tab = True
                                break
                            result = tap_tab(right_tab)
                            if result:
                                logger.debug(
                                    f"  -> 往右走，寻找 {tab}，点击 {right_tab} Tab"
                                )
                                return result

                    if not found_nav_tab:
                        logger.warning(f"  -> 无法找到任何 Tab 以导航至 {tab}，跳过")
                        self._visited_tabs.add(tab)

        # 3. 所有 Tab 完成，进入主题收藏
        if not self._theme_collection_done:
            theme_patterns = get_text_patterns("theme_collection")
            result = tap_text(self.adb, ocr_results, theme_patterns, wait=1.0)
            if result:
                logger.debug("  -> 进入主题收藏")
                self._theme_collection_done = True
                return result

        # 4. 全部完成，返回主页
        self._round_count += 1
        self._reset_tab_state()
        logger.debug(f"  -> 本轮领取完成，返回主页（第 {self._round_count} 轮）")

        close_patterns = get_text_patterns("close_button")
        result = click_close(self.adb, self.page_detector, ocr_results, close_patterns)
        if result:
            return result

        back_patterns = get_text_patterns("back_button")
        return navigate_back(self.adb, self.page_detector, ocr_results, back_patterns)

    def _try_claim_buttons(
        self, ocr_results: list[dict], screenshot
    ) -> ActionResult | None:
        """尝试点击可领取的按钮（全部領取/領取/達成）"""
        claim_patterns = get_text_patterns("reward_claim_buttons")

        for pattern in claim_patterns:
            for item in ocr_results:
                text = "".join(item["text"].lower().split())
                if "".join(pattern.lower().split()) == text:
                    box = item["box"]
                    if screenshot and is_button_clickable(
                        screenshot, box, threshold=0.4
                    ):
                        logger.debug(f"  -> 点击领取按钮: {pattern}")
                        return tap_box(self.adb, box, wait=1.0)
                    else:
                        logger.debug(f"  -> 按钮 {pattern} 已置灰，跳过")

        return None

    def _handle_theme_collection(self, page_info: dict) -> ActionResult:
        """处理主题收藏页面：领取后返回"""
        screenshot, ocr_results = self.page_detector.get_last_page_context()

        result = self._try_claim_buttons(ocr_results, screenshot)
        if result:
            return result

        # 无可领取，返回任务页面
        logger.debug("  -> 主题收藏领取完成，返回")
        back_patterns = get_text_patterns("back_button")
        return navigate_back(self.adb, self.page_detector, ocr_results, back_patterns)

    def _handle_reward_detail(self, page_info: dict) -> ActionResult:
        """处理奖励详情页面：点击達成按钮"""
        screenshot, ocr_results = self.page_detector.get_last_page_context()

        result = self._try_claim_buttons(ocr_results, screenshot)
        if result:
            return result

        logger.debug("  -> 奖励详情页面，等待...")
        return ActionResult.ok(wait=1.0)

    def _handle_home_icon(self, page_info: dict) -> ActionResult:
        """点击主页图标回到游戏主页"""
        logger.debug("  -> 点击主页图标回到游戏主页")
        return tap_home_icon(self.adb, self.page_detector, wait=3.0)
