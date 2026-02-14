# -*- coding: utf-8 -*-
"""
礼物盒领取任务模块

采用字典映射处理页面，使用 action_cache 管理页面内操作状态。
流程：主页检测礼物图标 → 进入礼物盒 → 领取礼物 → 返回主页
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
from ptcgp_auto_v2.utils.gesture import (
    navigate_back,
    normalize_text,
    quick_tap,
    tap_box,
    tap_text,
)

logger = logging.getLogger(__name__)

# ============================================================
# 常量定义（基于 1080x1920）
# ============================================================

# 过滤同行按钮的 y 坐标差值阈值
Y_THRESHOLD = 50

# 等待礼物盒加载时间 (s)
WAIT_GIFT_BOX_LOAD = 4.0

# 连续多少次无可领取则判断为完成
MAX_EMPTY_CHECK_ATTEMPTS = 2


# ============================================================
# 页面识别规则
# ============================================================


def _build_claim_gifts_pages() -> list[dict]:
    """构建礼物盒领取页面规则"""
    return [
        {
            # 礼物盒无可领取：任务完成
            "name": "gift_box_empty",
            "identifiers": get_text_patterns("gift_empty"),
            "priority": 5,
        },
        {
            # 游戏主页：检测是否有礼物图标的起点
            "name": "game_home_main",
            "match_all": True,
            "identifiers": get_text_patterns("game_home_main"),
            "priority": 10,
        },
        {
            # 卡牌登录页面：领取礼物后展示卡牌，需要向上滑动
            "name": "card_register_page",
            "identifiers": get_text_patterns("pack_card_register"),
            "priority": 12,
        },
        {
            # 送出谢谢弹窗：朋友礼物需要点击"謝謝！"确认
            "name": "popup_send_thanks",
            "identifiers": get_text_patterns("popup_send_thanks"),
            "priority": 13,
        },
        {
            # 礼物盒页面：有"禮物盒"标题
            "name": "gift_box_page",
            "identifiers": get_text_patterns("gift_box_page"),
            "priority": 15,
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
    pages = _build_claim_gifts_pages()

    def __init__(self, adb, recognizer, page_detector):
        super().__init__(adb, recognizer, page_detector)

        # 页面内操作缓存
        self._action_cache: dict[str, bool] = {}

        # 任务状态
        self._claim_attempt_count = 0  # 连续无可领取次数
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
        logger.info("礼物盒领取任务开始")
        self._action_cache.clear()
        self._claim_attempt_count = 0
        self._completed = False

    def is_completed(self) -> bool:
        """判断任务是否已完成"""
        return self._completed

    def handle_page(self, page_name: str, page_info: dict) -> ActionResult:
        """处理识别到的页面"""
        logger.debug(f"处理页面: {page_name}")

        # 页面处理器映射
        handlers = {
            "gift_box_empty": self._handle_gift_box_empty,
            "game_home_main": self._handle_home,
            "card_register_page": self._handle_card_register,
            "popup_send_thanks": self._handle_send_thanks,
            "gift_box_page": self._handle_gift_box,
        }

        handler = handlers.get(page_name)
        if handler:
            return handler(page_info)

        logger.warning(f"未处理的页面: {page_name}")
        return ActionResult.ok(wait=1.0)

    def on_complete(self, result: TaskResult):
        """任务完成后的处理"""
        logger.info(f"任务完成，结果: {'成功' if result.success else '失败'}")

    def handle_unknown_page(self, page_info) -> ActionResult:
        """未知页面兜底：点击屏幕上方，触发页面继续流转。"""
        logger.debug("未知页面，点击屏幕上方兜底")
        return quick_tap(self.adb, self.adb.center_x(), self.adb.scaled_y(10), times=3)

    # ============================================================
    # 页面处理方法
    # ============================================================

    def _handle_gift_box_empty(self, page_info: dict) -> ActionResult:
        """处理礼物盒空页面"""
        logger.info("  -> 检测到「沒有可領取的道具」，任务完成")
        self._completed = True
        return ActionResult.ok(wait=0.5)

    def _handle_home(self, page_info: dict) -> ActionResult:
        """处理主页：检测礼物图标"""
        self._reset_action_cache()

        screenshot, _ = self.page_detector.capture()
        if not screenshot:
            logger.warning("  -> 无法获取截图")
            return ActionResult.ok(wait=1.0)

        # 检测 icon_gift 模板
        gift_icon = self.page_detector.find_template_with_scale(
            "icon_gift", screenshot=screenshot
        )

        if gift_icon:
            logger.debug("  -> 检测到礼物图标，进入礼物盒页面")
            tap_box(self.adb, gift_icon.box, wait=1.0)
            time.sleep(WAIT_GIFT_BOX_LOAD)
            return ActionResult.ok(wait=1.0)

        # 未找到礼物图标，任务完成
        logger.debug("  -> 未检测到礼物图标，任务完成")
        self._completed = True
        return ActionResult.ok(wait=1.0)

    def _handle_card_register(self, page_info: dict) -> ActionResult:
        """处理卡牌登录页面：向上滑动登录卡牌"""
        return swipe_card_register(self.adb, wait=1.0)

    def _handle_send_thanks(self, page_info: dict) -> ActionResult:
        """处理送出谢谢弹窗：点击"謝謝！"按钮"""
        ocr_results = page_info.get("ocr_results", [])
        thanks_patterns = get_text_patterns("thanks_button")

        # 精确匹配「謝謝！」按钮
        result = tap_text(self.adb, ocr_results, thanks_patterns, wait=1.5, exact=True)
        if result:
            logger.debug("  -> 点击「謝謝！」按钮")
            return result

        logger.debug("  -> 未找到「謝謝！」按钮")
        return ActionResult.ok(wait=1.0)

    def _handle_gift_box(self, page_info: dict) -> ActionResult:
        """处理礼物盒页面：领取礼物"""
        ocr_results = page_info.get("ocr_results", [])

        # 尝试点击领取按钮
        result = self._try_claim_buttons(ocr_results)
        if result:
            self._claim_attempt_count = 0
            return result

        # 无可领取，检查是否真的没有礼物
        self._claim_attempt_count += 1
        if self._claim_attempt_count >= MAX_EMPTY_CHECK_ATTEMPTS:
            logger.debug("  -> 礼物领取完成，返回主页")
            self._reset_action_cache()
            back_patterns = get_text_patterns("back_button")
            return navigate_back(
                self.adb, self.page_detector, ocr_results, back_patterns
            )

        return ActionResult.ok(wait=1.0)

    def _try_claim_buttons(self, ocr_results: list[dict]) -> ActionResult | None:
        """
        尝试点击可领取的按钮

        按优先级：全部領取 > 領取
        过滤掉与"領取紀錄"同行的"領取" Tab 按钮
        """
        claim_patterns = get_text_patterns("gift_claim_buttons")
        record_patterns = get_text_patterns("gift_record")

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
