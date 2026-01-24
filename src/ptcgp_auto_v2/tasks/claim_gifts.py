# -*- coding: utf-8 -*-
"""
礼物盒领取任务模块

自动领取游戏中礼物盒里的所有礼物：
1. 在主页检测礼物图标
2. 进入礼物盒页面
3. 优先点击"全部領取"，然后点击单个"領取"按钮
4. 完成后返回主页
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
from ptcgp_auto_v2.utils.gesture import (
    navigate_back,
    swipe,
    swipe_card_coords,
    tap_home_icon,
    tap_text,
    tap_box,
    normalize_text,
)

logger = logging.getLogger(__name__)

# ============================================================
# 常量定义
# ============================================================

# 过滤同行按钮的 y 坐标差值阈值（基于 1080x1920）
Y_THRESHOLD = 50

# 等待礼物盒加载时间 (s)
WAIT_GIFT_BOX_LOAD = 4.0
# 卡牌登录图鉴滑动时长 (ms)
SWIPE_DURATION_REGISTER = 300
# 连续多少次无可领取则判断为完成
MAX_EMPTY_CHECK_ATTEMPTS = 2


class ClaimGiftsPhase(Enum):
    """礼物领取阶段"""

    INIT = auto()  # 初始化
    NAVIGATING_TO_HOME = auto()  # 导航到主页
    CHECKING_HOME = auto()  # 在主页检查是否有礼物图标
    ENTERING_GIFTS = auto()  # 进入礼物盒页面
    CLAIMING_GIFTS = auto()  # 领取礼物中
    RETURNING_HOME = auto()  # 返回主页
    NO_GIFTS = auto()  # 无礼物，任务完成


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
def _build_claim_gifts_pages(text_patterns: dict) -> list[dict]:
    """构建礼物盒领取页面规则"""
    return [
        {
            # 礼物盒无可领取：任务完成
            "name": "gift_box_empty",
            "identifiers": _get_patterns(text_patterns, "gift_empty"),
            "priority": 5,
        },
        {
            # 游戏主页：检测是否有礼物图标的起点
            "name": "game_home_main",
            "match_all": True,
            "identifiers": _get_patterns(text_patterns, "game_home_main"),
            "priority": 10,
        },
        {
            # 卡牌登录页面：领取礼物后展示卡牌，需要向上滑动
            "name": "card_register_page",
            "identifiers": _get_patterns(text_patterns, "pack_card_register"),
            "priority": 12,
        },
        {
            # 送出谢谢弹窗：朋友礼物需要点击"謝謝！"确认
            "name": "send_thanks_popup",
            "identifiers": _get_patterns(text_patterns, "gift_send_thanks"),
            "priority": 13,
        },
        {
            # 礼物盒页面：有"禮物盒"标题
            "name": "gift_box_page",
            "identifiers": _get_patterns(text_patterns, "gift_box_page"),
            "priority": 15,
        },
        {
            # 通用 home_icon：可点击回主页
            "name": "home_icon",
            "templates": ["icon_home"],
            "priority": 50,
        },
    ]


@TaskRegistry.register("claim_gifts")
class ClaimGiftsTask(Task):
    """
    礼物盒领取任务

    自动领取游戏中礼物盒里的所有礼物。
    """

    task_type = "claim_gifts"
    reset_type = ResetType.DAILY
    max_iterations = 100
    max_unknown_pages = 15
    pages = _build_claim_gifts_pages(TEXT_PATTERNS)

    def __init__(self, adb, recognizer, page_detector):
        super().__init__(adb, recognizer, page_detector)

        # 核心状态机
        self._phase = ClaimGiftsPhase.INIT
        self._claim_attempt_count = 0  # 领取尝试次数（用于判断无礼物）

    def on_start(self):
        """任务开始前的初始化"""
        self._phase = ClaimGiftsPhase.NAVIGATING_TO_HOME
        logger.info(f"礼物盒领取任务开始，当前阶段: {self._phase.name}")

    def is_completed(self) -> bool:
        """判断任务是否已完成"""
        return self._phase == ClaimGiftsPhase.NO_GIFTS

    def handle_page(self, page_name: str, page_info: dict) -> ActionResult:
        """处理识别到的页面"""
        logger.debug(f"处理页面: {page_name}, 当前阶段: {self._phase.name}")

        # 礼物盒无可领取：任务完成
        if page_name == "gift_box_empty":
            logger.info("  -> 检测到「沒有可領取的道具」，任务完成")
            self._phase = ClaimGiftsPhase.NO_GIFTS
            return ActionResult.ok(wait=0.5)

        # 主页：检测是否有礼物图标
        if page_name == "game_home_main":
            return self._handle_home(page_info)

        # 卡牌登录页面：向上滑动登录卡牌
        if page_name == "card_register_page":
            return self._handle_card_register(page_info)

        # 送出谢谢弹窗：点击"謝謝！"按钮
        if page_name == "send_thanks_popup":
            return self._handle_send_thanks(page_info)

        # 礼物盒页面：领取礼物
        if page_name == "gift_box_page":
            return self._handle_gift_box(page_info)

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
            f"任务完成，阶段: {self._phase.name}, "
            f"结果: {'成功' if result.success else '失败'}"
        )

    def _handle_home(self, page_info: dict) -> ActionResult:
        """
        处理主页：点击礼物图标
        """
        self._phase = ClaimGiftsPhase.CHECKING_HOME

        screenshot, _ = self.page_detector.capture()
        if not screenshot:
            logger.warning("  -> 无法获取截图")
            return ActionResult.ok(wait=1.0)

        # 检测 icon_gift 模板
        gift_icon = self.page_detector.find_template_with_scale(
            "icon_gift",
            screenshot=screenshot,
        )

        if gift_icon:
            # 有礼物，点击进入
            logger.debug("  -> 检测到礼物图标，进入礼物盒页面")
            self._phase = ClaimGiftsPhase.ENTERING_GIFTS
            tap_box(self.adb, gift_icon.box, wait=1.0)
            time.sleep(WAIT_GIFT_BOX_LOAD)
            return ActionResult.ok(wait=1.0)

        # 未找到礼物图标，直接结束
        logger.debug("  -> 未检测到礼物图标，任务完成")
        self._phase = ClaimGiftsPhase.NO_GIFTS
        return ActionResult.ok(wait=1.0)

    def _handle_card_register(self, page_info: dict) -> ActionResult:
        """
        处理卡牌登录页面：向上滑动登录卡牌

        领取礼物后可能展示新卡牌，需要向上滑动将卡牌登录至图�的。
        """
        logger.debug("  -> 卡牌登录页面，向上滑动登录卡牌")
        start, end = swipe_card_coords(self.adb)
        return swipe(self.adb, start, end, duration=SWIPE_DURATION_REGISTER, wait=1.0)

    def _handle_send_thanks(self, page_info: dict) -> ActionResult:
        """
        处理送出谢谢弹窗：点击"謝謝！"按钮

        朋友礼物需要点击"謝謝！"确认后才能完成领取。
        """
        ocr_results = page_info.get("ocr_results", [])
        thanks_patterns = _get_patterns(TEXT_PATTERNS, "gift_thanks_button")

        # 精确匹配「謝謝！」按钮
        result = tap_text(self.adb, ocr_results, thanks_patterns, wait=1.5, exact=True)
        if result:
            logger.debug("  -> 点击「謝謝！」按钮")
            return result

        # 未找到按钮，等待
        logger.debug("  -> 未找到「謝謝！」按钮")
        return ActionResult.ok(wait=1.0)

    def _handle_gift_box(self, page_info: dict) -> ActionResult:
        """
        处理礼物盒页面

        1. 优先点击"全部領取"
        2. 然后点击单个"領取"按钮（过滤掉与"領取紀錄"同行的 Tab 按钮）
        3. 无可领取时返回主页
        """
        self._phase = ClaimGiftsPhase.CLAIMING_GIFTS
        ocr_results = page_info.get("ocr_results", [])

        # 1. 尝试点击领取按钮
        result = self._try_claim_buttons(ocr_results)
        if result:
            self._claim_attempt_count = 0
            return result

        # 2. 无可领取，检查是否真的没有礼物
        self._claim_attempt_count += 1
        if self._claim_attempt_count >= MAX_EMPTY_CHECK_ATTEMPTS:
            # 连续 2 次无可点击，返回主页
            logger.debug("  -> 礼物领取完成，返回主页")
            self._phase = ClaimGiftsPhase.RETURNING_HOME
            back_patterns = _get_patterns(TEXT_PATTERNS, "back_button")
            return navigate_back(
                self.adb, self.page_detector, ocr_results, back_patterns
            )

        return ActionResult.ok(wait=1.0)

    def _try_claim_buttons(self, ocr_results: list[dict]) -> ActionResult | None:
        """
        尝试点击可领取的按钮

        按优先级：全部領取 > 領取
        过滤掉与"領取紀錄"同行的"領取" Tab 按钮

        Returns:
            ActionResult 如果成功点击，否则 None
        """
        claim_patterns = _get_patterns(TEXT_PATTERNS, "gift_claim_buttons")
        record_patterns = _get_patterns(TEXT_PATTERNS, "gift_record")

        # 获取"領取紀錄"的 y 坐标（用于过滤 Tab 按钮）
        record_y = None
        for item in ocr_results:
            text = normalize_text(item["text"])
            for pattern in record_patterns:
                if normalize_text(pattern) in text:
                    box = item["box"]
                    record_y = (box[1] + box[3]) // 2
                    break
            if record_y:
                break

        # 按优先级遍历领取按钮
        for pattern in claim_patterns:
            for item in ocr_results:
                text = normalize_text(item["text"])
                if normalize_text(pattern) == text:
                    box = item["box"]
                    button_y = (box[1] + box[3]) // 2

                    # 过滤与"領取紀錄"同行的"領取" Tab 按钮
                    if (
                        record_y
                        and pattern != "全部領取"
                        and abs(button_y - record_y) < Y_THRESHOLD
                    ):
                        logger.debug(f"  -> 跳过 Tab 按钮: {pattern} @ y={button_y}")
                        continue

                    logger.debug(f"  -> 点击领取按钮: {pattern}")
                    return tap_box(self.adb, box, wait=1.5)

        return None
