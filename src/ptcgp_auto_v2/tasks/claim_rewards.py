# -*- coding: utf-8 -*-
"""
任务奖励领取任务模块

自动领取游戏中的所有任务奖励：
1. 检测主页是否有奖励图标
2. 遍历所有 Tab（每日/图鉴/牌组/掉落）领取奖励
3. 进入主题收藏领取奖励
4. 最多执行 3 轮
"""

import logging
import time
from enum import Enum, auto

from ptcgp_auto_v2.core.task_base import (
    ActionResult,
    ResetType,
    Task,
    TaskRegistry,
    TaskResult,
)
from ptcgp_auto_v2.locales.zh_Hant import TEXT_PATTERNS
from ptcgp_auto_v2.utils.color import is_button_clickable
from ptcgp_auto_v2.utils.gesture import (
    click_close,
    navigate_back,
    tap_home_icon,
    tap_text,
    tap_box,
    is_text_visible,
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
# FIXED_TABS: 常驻 Tab，必须点击
# DYNAMIC_TABS: 动态 Tab (如掉落)，可能不存在
# WALL_TAB: 边界 Tab (特级)，用于判断是否到达最右侧，不点击
FIXED_TABS = ["daily", "collection", "deck"]
DYNAMIC_TABS = ["drop"]
WALL_TAB = "premium"
TAB_ORDER = FIXED_TABS + DYNAMIC_TABS + [WALL_TAB]


class ClaimRewardsPhase(Enum):
    """任务奖励领取阶段"""

    INIT = auto()  # 初始化
    NAVIGATING_TO_HOME = auto()  # 导航到主页
    CHECKING_HOME = auto()  # 在主页检查是否有奖励
    ENTERING_REWARDS = auto()  # 进入任务奖励页面
    CLAIMING_TAB = auto()  # 在某个 Tab 领取奖励
    CLAIMING_THEME_COLLECTION = auto()  # 领取主题收藏奖励
    RETURNING_HOME = auto()  # 返回主页
    NO_REWARDS = auto()  # 确认无奖励，任务完成


def _get_patterns(text_patterns: dict, key: str) -> list[str]:
    """获取指定配置的文本列表"""
    patterns = text_patterns.get(key, [])
    if isinstance(patterns, list):
        return patterns
    return []


# ============================================================
# 页面识别规则
# 注意：priority 数值越小优先级越高
# ============================================================
def _build_claim_rewards_pages(text_patterns: dict) -> list[dict]:
    """构建任务奖励领取页面规则"""
    return [
        {
            # 游戏主页：检测是否有奖励图标的起点
            "name": "game_home_main",
            "match_all": True,
            "identifiers": _get_patterns(text_patterns, "game_home_main"),
            "priority": 10,
        },
        {
            # 任务奖励页面：底部有 Tab 栏（每日/圖鑑/牌組/掉落）
            # 优先匹配，因为主题收藏页面没有这些 Tab
            # exact_match: 避免弹窗文字（如"已獲得新的租用牌組"）误匹配
            "name": "rewards_page",
            "identifiers": _get_patterns(text_patterns, "rewards_page_tabs"),
            "exact_match": True,
            "priority": 15,
        },
        {
            # 奖励详情页面：点击領取后展示卡牌的页面，有"達成！"按钮
            # match_all: 必须同时有"報酬"和"達成！"才匹配
            "name": "reward_detail_page",
            "identifiers": _get_patterns(text_patterns, "reward_detail_page"),
            "match_all": True,
            "priority": 16,
        },
        {
            # 主题收藏页面：有"主題收藏"标题，但没有 Tab 栏
            # 由于 rewards_page 优先级更高，有 Tab 时不会匹配到这里
            "name": "theme_collection_page",
            "identifiers": _get_patterns(text_patterns, "theme_collection"),
            "priority": 20,
        },
        {
            # 通用 home_icon：可点击回主页
            "name": "home_icon",
            "templates": ["icon_home"],
            "priority": 50,
        },
    ]


@TaskRegistry.register("claim_rewards")
class ClaimRewardsTask(Task):
    """
    任务奖励领取任务

    自动领取游戏中的所有任务奖励，包括：
    - 每日任务奖励
    - 图鉴任务奖励
    - 牌组任务奖励
    - 掉落活动奖励（如果存在）
    - 主题收藏奖励
    """

    task_type = "claim_rewards"
    reset_type = ResetType.DAILY
    max_iterations = 150
    max_unknown_pages = 15
    pages = _build_claim_rewards_pages(TEXT_PATTERNS)

    def __init__(self, adb, recognizer, page_detector):
        super().__init__(adb, recognizer, page_detector)

        # 核心状态机
        self._phase = ClaimRewardsPhase.INIT
        self._home_check_count = 0  # 主页无奖励检查次数
        self._round_count = 0  # 当前领取轮数

        # Tab 遍历状态：记录本轮已访问的 Tab
        self._visited_tabs: set[str] = set()
        self._theme_collection_done = False  # 主题收藏是否已处理
        self._going_left = True  # 是否处于往左走阶段

    def on_start(self):
        """任务开始前的初始化"""
        self._phase = ClaimRewardsPhase.NAVIGATING_TO_HOME
        logger.info(f"任务奖励领取任务开始，当前阶段: {self._phase.name}")

    def is_completed(self) -> bool:
        """判断任务是否已完成"""
        return self._phase == ClaimRewardsPhase.NO_REWARDS

    def handle_page(self, page_name: str, page_info: dict) -> ActionResult:
        """处理识别到的页面"""
        logger.debug(f"处理页面: {page_name}, 当前阶段: {self._phase.name}")

        # 主页：检测是否有奖励图标
        if page_name == "game_home_main":
            return self._handle_home(page_info)

        # 任务奖励页面：遍历 Tab 并领取
        if page_name == "rewards_page":
            return self._handle_rewards_page(page_info)

        # 奖励详情页面：点击達成按钮
        if page_name == "reward_detail_page":
            return self._handle_reward_detail(page_info)

        # 主题收藏页面：领取后返回
        if page_name == "theme_collection_page":
            return self._handle_theme_collection(page_info)

        # home_icon：点击回主页
        if page_name == "home_icon":
            logger.debug("  -> 点击主页图标回到游戏主页")
            return tap_home_icon(self.adb, self.page_detector, wait=3.0)

        # 其他页面
        logger.warning(f"未处理的页面: {page_name}")
        return ActionResult.ok(wait=1.0)

    def on_complete(self, result: TaskResult):
        """任务完成后的处理"""
        logger.info(
            f"任务完成，阶段: {self._phase.name}, 轮数: {self._round_count}, "
            f"结果: {'成功' if result.success else '失败'}"
        )

    def _handle_home(self, page_info: dict) -> ActionResult:
        """
        处理主页：核心决策点

        检测是否有奖励图标：
        1. 有奖励 → 进入任务页面
        2. 无奖励 → 连续检测 2 次（每次间隔 2 秒），全部无奖励才确认
        """
        self._phase = ClaimRewardsPhase.CHECKING_HOME

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
                "icon_has_reward",
                screenshot=screenshot,
            )

            if reward_icon:
                # 有奖励，点击进入
                logger.debug("  -> 检测到奖励图标，进入任务页面")
                self._home_check_count = 0
                self._phase = ClaimRewardsPhase.ENTERING_REWARDS
                return tap_box(self.adb, reward_icon.box, wait=3.0)

            logger.debug(f"  -> 未检测到奖励图标 ({i + 1}/{rounds})")
            if i < rounds - 1:
                time.sleep(interval)

        # 2 次都无奖励，累计检查次数
        self._home_check_count += 1
        logger.debug(f"  -> 确认无奖励图标（第 {self._home_check_count} 轮检查）")

        if self._home_check_count >= rounds or self._round_count >= MAX_ROUNDS:
            logger.debug("  -> 确认无奖励，任务完成")
            self._phase = ClaimRewardsPhase.NO_REWARDS

        return ActionResult.ok(wait=1.0)

    def _try_claim_buttons(
        self, ocr_results: list[dict], screenshot
    ) -> ActionResult | None:
        """
        尝试点击可领取的按钮（全部領取/領取/達成）

        检测按钮颜色，只点击绿色（可点击）的按钮

        Returns:
            ActionResult 如果成功点击，否则 None
        """
        claim_patterns = TEXT_PATTERNS.get("reward_claim_buttons", [])

        for pattern in claim_patterns:
            for item in ocr_results:
                text = "".join(item["text"].lower().split())
                if "".join(pattern.lower().split()) == text:
                    box = item["box"]
                    if screenshot and is_button_clickable(screenshot, box, threshold=0.1):
                        logger.debug(f"  -> 点击领取按钮: {pattern}")
                        return tap_box(self.adb, box, wait=1.0)
                    else:
                        logger.debug(f"  -> 按钮 {pattern} 已置灰，跳过")

        return None

    def _handle_rewards_page(self, page_info: dict) -> ActionResult:
        """
        处理任务奖励页面

        1. 尝试点击领取按钮（全部領取/領取/達成），需检测按钮颜色
        2. 无可领取时切换到下一个 Tab
        3. 所有 Tab 完成后进入主题收藏
        4. 全部完成后返回主页
        """
        self._phase = ClaimRewardsPhase.CLAIMING_TAB
        screenshot, ocr_results = self.page_detector.get_last_page_context()

        # 1. 尝试点击领取按钮
        result = self._try_claim_buttons(ocr_results, screenshot)
        if result:
            return result

        # 2. 当前 Tab 无可领取，切换 Tab
        tab_patterns_map = {
            tab: TEXT_PATTERNS.get(f"rewards_tab_{tab}", []) for tab in TAB_ORDER
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
            # 检查特级 (WALL_TAB) 是否可见，作为"是否到达最右侧"的标志
            wall_visible = is_visible(WALL_TAB)

            for tab in TAB_ORDER:
                # 1. 遇到 WALL_TAB (Premium)，意味着遍历结束
                if tab == WALL_TAB:
                    # 无论可见与否，WALL_TAB 本身不需要点击，且它是列表最后一个
                    # 到了这里说明前面的 Tab 都处理完了（或被跳过了）
                    # 停止遍历，进入下一步（主题收藏）
                    break

                if tab in self._visited_tabs:
                    continue

                # 2. 如果当前 Tab 可见，点击它
                if is_visible(tab):
                    result = tap_tab(tab)
                    if result:
                        logger.debug(f"  -> 点击 {tab} Tab")
                        self._visited_tabs.add(tab)
                        return result

                # 3. 如果当前 Tab 不可见
                else:
                    # Case A: 已经看到了墙 (WALL_TAB)
                    # 说明已经到了最右边，但还没看到目标 Tab -> 目标 Tab 不存在
                    if wall_visible:
                        logger.debug(f"  -> 已达最右 (看到 {WALL_TAB}) 但未见 {tab}，跳过")
                        self._visited_tabs.add(tab)
                        continue

                    # Case B: 还没看到墙
                    # 说明还需要向右滑动/寻找
                    # 尝试点击屏幕上最右侧可见的 Tab（排除 WALL_TAB 本身，虽然它不可见）
                    # 注意：我们这里从 TAB_ORDER 倒序找第一个可见的 Tab 点击
                    for right_tab in reversed(TAB_ORDER):
                        if right_tab == WALL_TAB:
                            continue # 不点击墙

                        if is_visible(right_tab):
                            result = tap_tab(right_tab)
                            if result:
                                logger.debug(f"  -> 往右走，寻找 {tab}，点击 {right_tab} Tab")
                                return result

                    # Case C: 找不到任何可见 Tab（异常）
                    logger.warning(f"  -> 无法找到任何 Tab 以导航至 {tab}，跳过")
                    self._visited_tabs.add(tab)

        # 3. 所有 Tab 完成，进入主题收藏
        if not self._theme_collection_done:
            theme_patterns = TEXT_PATTERNS.get("theme_collection", [])
            result = tap_text(self.adb, ocr_results, theme_patterns, wait=1.0)
            if result:
                logger.debug("  -> 进入主题收藏")
                self._phase = ClaimRewardsPhase.CLAIMING_THEME_COLLECTION
                self._theme_collection_done = True
                return result

        # 4. 全部完成，返回主页
        self._round_count += 1
        self._reset_tab_state()
        logger.debug(f"  -> 本轮领取完成，返回主页（第 {self._round_count} 轮）")

        close_patterns = TEXT_PATTERNS.get("close_button", [])
        result = click_close(self.adb, self.page_detector, ocr_results, close_patterns)
        if result:
            self._phase = ClaimRewardsPhase.RETURNING_HOME
            return result

        back_patterns = TEXT_PATTERNS.get("back_button", [])
        return navigate_back(self.adb, self.page_detector, ocr_results, back_patterns)

    def _reset_tab_state(self):
        """重置 Tab 遍历状态（用于下一轮）"""
        self._visited_tabs.clear()
        self._theme_collection_done = False
        self._going_left = True

    def _handle_theme_collection(self, page_info: dict) -> ActionResult:
        """处理主题收藏页面：领取后返回"""
        self._phase = ClaimRewardsPhase.CLAIMING_THEME_COLLECTION
        screenshot, ocr_results = self.page_detector.get_last_page_context()

        result = self._try_claim_buttons(ocr_results, screenshot)
        if result:
            return result

        # 无可领取，返回任务页面
        logger.debug("  -> 主题收藏领取完成，返回")
        back_patterns = TEXT_PATTERNS.get("back_button", [])
        return navigate_back(self.adb, self.page_detector, ocr_results, back_patterns)

    def _handle_reward_detail(self, page_info: dict) -> ActionResult:
        """处理奖励详情页面：点击達成按钮"""
        screenshot, ocr_results = self.page_detector.get_last_page_context()

        # 尝试点击達成按钮
        result = self._try_claim_buttons(ocr_results, screenshot)
        if result:
            return result

        # 没有按钮可点，等待
        logger.debug("  -> 奖励详情页面，等待...")
        return ActionResult.ok(wait=1.0)
