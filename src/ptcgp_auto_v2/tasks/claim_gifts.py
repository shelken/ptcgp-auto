# -*- coding: utf-8 -*-
"""
礼物盒领取任务模块

采用字典映射处理页面，使用 action_cache 管理页面内操作状态。
流程：主页检测礼物图标 → 进入礼物盒 → 领取礼物 → 处理开包 → 识别记录 → 返回主页

继承 PackOpeningTaskBase，补齐开包识别与开包记录落库，pack_type 使用 gift_box。
"""

import logging
import time
from typing import cast

from ptcgp_auto_v2.core.task_base import (
    ActionResult,
    ResetType,
    TaskRegistry,
    TaskResult,
)
from ptcgp_auto_v2.db.models import PackRecordType
from ptcgp_auto_v2.locales import get_text_patterns
from ptcgp_auto_v2.tasks.pack_opening_task_base import (
    PackOpeningTaskBase,
    build_pack_opening_pages,
)
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

# 領取紀錄 行过滤阈值（像素）
Y_THRESHOLD = 50

# 等待礼物盒加载时间 (s)
WAIT_GIFT_BOX_LOAD = 4.0

# 连续多少次无可领取则判断为完成
MAX_EMPTY_CHECK_ATTEMPTS = 2


# ============================================================
# 页面识别规则
# ============================================================


def _build_claim_gifts_pages() -> list[dict]:
    """构建礼物盒领取页面规则（合并通用开包页面）"""
    task_specific_pages = [
        # 沒有可領取的道具
        {
            "name": "gift_box_empty",
            "identifiers": get_text_patterns("gift_empty"),
            "priority": 5,
        },
        # 商店 / 得卡挑戰
        {
            "name": "game_home_main",
            "match_all": True,
            "identifiers": get_text_patterns("game_home_main"),
            "priority": 10,
        },
        # 要送出「謝謝！」嗎
        {
            "name": "popup_send_thanks",
            "identifiers": get_text_patterns("popup_send_thanks"),
            "priority": 13,
        },
        # 禮物盒
        {
            "name": "gift_box_page",
            "identifiers": get_text_patterns("gift_box_page"),
            "priority": 15,
        },
    ]
    return task_specific_pages + build_pack_opening_pages()


@TaskRegistry.register("claim_gifts")
class ClaimGiftsTask(PackOpeningTaskBase):
    """
    礼物盒领取任务

    自动领取游戏中礼物盒里的所有礼物，处理可能包含的卡包礼物，
    使用统一开包流程进行识别和记录保存。
    """

    task_type = "claim_gifts"
    reset_type = ResetType.DAILY
    max_iterations = 200
    pages = _build_claim_gifts_pages()

    def __init__(self, adb, recognizer, page_detector):
        super().__init__(adb, recognizer, page_detector)

    # ============================================================
    # 扩展点实现（PackOpeningTaskBase 要求）
    # ============================================================

    def get_pack_record_type(self) -> str:
        """返回 pack 记录类型：礼物盒"""
        return PackRecordType.GIFT_BOX

    def get_rare_card_notify_message(self) -> str:
        """返回稀有卡通知消息：礼物盒领取"""
        return "礼物获得稀有卡牌"

    def should_prepare_pack_resources(self) -> bool:
        """礼物盒不需要准备卡包图片资源"""
        return False

    # ============================================================
    # 任务生命周期
    # ============================================================

    def on_start(self):
        """任务开始前的初始化"""
        logger.info("礼物盒领取任务开始")

        self._init_repositories()
        self.state.reset()
        self.state_set("claim_attempt_count", 0)
        self._packs_opened_count = 0
        self._result_recognized = False

    def handle_unmapped_page(self, page_name: str, page_info: dict) -> ActionResult:
        logger.debug(f"处理页面: {page_name}")
        logger.warning(f"未处理的页面: {page_name}")
        return ActionResult.ok(wait=1.0)

    def handle_unknown_page(self, page_info) -> ActionResult:
        """未知页面兜底：点击屏幕上方，触发页面继续流转。"""
        logger.debug("未知页面，点击屏幕上方兜底")
        return quick_tap(self.adb, self.adb.center_x(), self.adb.scaled_y(10))

    def on_complete(self, result: TaskResult):
        """任务完成后的处理"""
        logger.info(f"任务完成，结果: {'成功' if result.success else '失败'}")
        # 清理开包推断会话资源（无论成功与否）
        self.finalize_pack_session()

    # ============================================================
    # 页面处理方法（任务特定）
    # ============================================================

    def _handle_gift_box_empty(self, page_info: dict) -> ActionResult:
        """处理礼物盒空页面"""
        logger.info("  -> 检测到「沒有可領取的道具」，任务完成")
        self.complete()
        return ActionResult.ok(wait=0.5)

    def _handle_game_home_main(self, page_info: dict) -> ActionResult:
        """处理主页：检测礼物图标"""
        self.reset_action_cache()

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
        self.complete()
        return ActionResult.ok(wait=1.0)

    def _handle_popup_send_thanks(self, page_info: dict) -> ActionResult:
        """处理送出谢谢弹窗：点击"謝謝！"按钮"""
        ocr_results = page_info.get("ocr_results", [])
        thanks_patterns = get_text_patterns("thanks_button")

        # 精确匹配「謝謝！」按钮
        result = tap_text(self.adb, ocr_results, thanks_patterns, wait=1.5, exact=True)
        if result:
            logger.info("  -> 点击「謝謝！」按钮")
            return result

        logger.debug("  -> 未找到「謝謝！」按钮")
        return ActionResult.ok(wait=1.0)

    def _handle_gift_box_page(self, page_info: dict) -> ActionResult:
        """处理礼物盒页面：领取礼物"""
        ocr_results = page_info.get("ocr_results", [])

        # 尝试点击领取按钮
        result = self._try_claim_buttons(ocr_results)
        if result:
            self.state_set("claim_attempt_count", 0)
            return result

        # 无可领取，检查是否真的没有礼物
        claim_attempt_count = int(self.state_get("claim_attempt_count", 0)) + 1
        self.state_set("claim_attempt_count", claim_attempt_count)
        if claim_attempt_count >= MAX_EMPTY_CHECK_ATTEMPTS:
            logger.debug("  -> 礼物领取完成，返回主页")
            self.reset_action_cache()
            return navigate_back(self.adb, self.page_detector, ocr_results)

        return ActionResult.ok(wait=1.0)

    def _filter_ocr_results_by_record(
        self, ocr_results: list[dict], record_patterns: list[str]
    ) -> list[dict]:
        """按「領取紀錄」位置过滤 OCR：移除阈值线以下（含）项。"""
        normalized_record_patterns = [
            normalize_text(pattern) for pattern in record_patterns
        ]
        record_y = next(
            (
                (item["box"][1] + item["box"][3]) // 2
                for item in ocr_results
                if any(
                    pattern in normalize_text(item["text"])
                    for pattern in normalized_record_patterns
                )
            ),
            None,
        )
        if record_y is None:
            return ocr_results

        cutoff_y = record_y - Y_THRESHOLD
        return [
            item
            for item in ocr_results
            if ((item["box"][1] + item["box"][3]) // 2) < cutoff_y
        ]

    def _try_claim_buttons(self, ocr_results: list[dict]) -> ActionResult | None:
        """
        尝试点击可领取的按钮

        按固定顺序：先全部領取，再領取
        如果识别到"領取紀錄"，过滤掉其阈值线以下（含）的 OCR 项
        """
        claim_patterns = get_text_patterns("gift_claim_buttons")
        record_patterns = get_text_patterns("gift_record")
        if not claim_patterns:
            return None

        claim_all_patterns = claim_patterns[:1]
        single_claim_patterns = claim_patterns[1:]
        filtered_ocr_results = self._filter_ocr_results_by_record(
            ocr_results, record_patterns
        )

        wait = 1.5
        claim_all_result = tap_text(
            self.adb,
            filtered_ocr_results,
            claim_all_patterns,
            wait=0.0,
            exact=True,
        )
        single_result = tap_text(
            self.adb,
            filtered_ocr_results,
            single_claim_patterns,
            wait=wait,
            exact=True,
        )

        if single_result:
            return single_result
        if claim_all_result:
            return ActionResult.ok(wait=wait)
        return None
