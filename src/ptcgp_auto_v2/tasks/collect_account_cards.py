# -*- coding: utf-8 -*-
"""
收集账号高稀有度卡牌信息任务

流程：主页 -> 卡牌页 -> 筛选高稀有度 -> 排序为最新 -> 识别卡牌 -> 记录数据
"""

import logging
import time
from enum import Enum, auto
from typing import Optional, cast

from ptcgp_auto_v2.config.constants import HIGH_RARITY_TARGETS, SWIPE_STEPS_SCROLL
from ptcgp_auto_v2.core.task_base import (
    ActionResult,
    ResetType,
    TaskRegistry,
)
from ptcgp_auto_v2.core.stateful_task import StatefulTask
from ptcgp_auto_v2.infra.card_hash_manager import get_card_hash_manager
from ptcgp_auto_v2.infra.icon_group_detector import IconGroupDetector
from ptcgp_auto_v2.infra.model_manager import get_model_manager
from ptcgp_auto_v2.infra.yolo_card_recognizer import YoloCardRecognizer
from ptcgp_auto_v2.locales import get_text_patterns
from ptcgp_auto_v2.tasks.utils.rarity_filter import (
    FilterPanelState,
    handle_filter_panel,
)
from ptcgp_auto_v2.utils.card_name_resolver import resolve_card_name
from ptcgp_auto_v2.utils.gesture import (
    click_close,
    pinch_in,
    scroll_points,
    swipe,
    tap,
    tap_box,
    tap_template,
    tap_text,
)

logger = logging.getLogger(__name__)


# ============================================================
# 常量定义（基于 1080x1920 基准分辨率）
# ============================================================

BASE_SCAN_SCROLL_DISTANCE_Y = 500  # 1920 * 0.26
BASE_SORT_ROW_TOL = 30
BASE_SORT_BTN_X = 965
BASE_SORT_BTN_Y = 1672


class CollectPhase(Enum):
    """收集任务阶段"""

    ENTER = auto()
    FILTER = auto()
    SORT = auto()
    SCAN = auto()
    COMPLETED = auto()


def _build_collect_pages() -> list[dict]:
    return [
        {
            "name": "card_filter_panel",
            "identifiers": get_text_patterns("card_filter_title"),
            "exact_match": True,
            "priority": 5,
        },
        {
            "name": "card_sort_panel",
            "identifiers": get_text_patterns("card_sort_title"),
            "exact_match": True,
            "priority": 6,
        },
        {
            "name": "card_page_own",
            "templates": ["icon_bottom_card_clicked"],
            "template_threshold": 0.8,
            "priority": 10,
        },
        {
            "name": "card_entry_icon",
            "templates": ["icon_bottom_card"],
            "priority": 20,
        },
        {
            "name": "game_home_main",
            "identifiers": get_text_patterns("game_home_main"),
            "match_all": True,
            "priority": 30,
        },
    ]


@TaskRegistry.register("collect_account_cards")
class CollectAccountCardsTask(StatefulTask):
    """收集当前账号高稀有度卡牌信息"""

    task_type = "collect_account_cards"
    reset_type = ResetType.DAILY
    max_iterations = 100
    max_same_page_rounds = max_iterations
    pages = _build_collect_pages()

    def __init__(self, adb, recognizer, page_detector):
        super().__init__(adb, recognizer, page_detector)

        self.card_recognizer = YoloCardRecognizer(
            adb=adb,
            model_manager=get_model_manager(),
            hash_manager=get_card_hash_manager(),
        )
        self.icon_detector = IconGroupDetector(
            template_matcher=page_detector.template_matcher
        )

        self._account_card_repo = None
        self._card_repo = None

    def on_start(self):
        from ptcgp_auto_v2.db.repositories import AccountCardRepository, CardRepository

        self._account_card_repo = AccountCardRepository()
        self._card_repo = CardRepository()

        self.state.reset()
        self.state_update(
            {
                "filter_state": FilterPanelState(),
                "phase": CollectPhase.ENTER,
                "last_signature": None,
                "last_detect_signature": None,
                "pending_cards": {},
                "pending_order": [],
                "consecutive_all_owned": 0,
                "filter_action_cache": {},
            }
        )

        if self.account.id is None:
            logger.error("账号 ID 为空，无法执行收集任务")
            self.skip("账号 ID 为空")

    def handle_unknown_page(self, page_info) -> ActionResult:
        logger.debug("未知页面，等待后重试")
        return ActionResult.wait(0.5)

    def _handle_game_home_main(self, page_info: dict) -> ActionResult:
        return self._handle_card_entry_icon(page_info)

    def _handle_card_entry_icon(self, page_info: dict) -> ActionResult:
        result = tap_template(
            self.adb, self.page_detector, "icon_bottom_card", wait=1.0
        )
        return result or ActionResult.ok(wait=1.0)

    def _handle_card_page_own(self, page_info: dict) -> ActionResult:
        phase = cast(CollectPhase, self.state_get("phase", CollectPhase.ENTER))
        logger.info("进入卡牌页处理，当前阶段: %s", phase.name)
        if not self.is_action_done("filter_applied"):
            self.state_set("phase", CollectPhase.FILTER)
            result = tap_template(self.adb, self.page_detector, "icon_search", wait=1.0)
            if result:
                return result
            fallback = self.page_detector.find_template("icon_search", threshold=0.6)
            if fallback:
                return tap_box(self.adb, fallback, wait=1.0)
            return ActionResult.ok(wait=1.0)

        if not self.is_action_done("sort_ready"):
            self.state_set("phase", CollectPhase.SORT)
            return self._tap_sort_button()

        self.state_set("phase", CollectPhase.SCAN)
        return self._scan_and_scroll(page_info)

    def _handle_card_filter_panel(self, page_info: dict) -> ActionResult:
        # 使用统一的 action 状态，与 handle_filter_panel 内部共用同一套缓存
        action_cache = cast(
            dict[str, bool], self.state_get("filter_action_cache", {})
        )
        result = handle_filter_panel(
            adb=self.adb,
            page_detector=self.page_detector,
            icon_detector=self.icon_detector,
            page_info=page_info,
            rarity_codes=HIGH_RARITY_TARGETS,
            state=cast(FilterPanelState, self.state_get("filter_state")),
            action_cache=action_cache,
        )
        # 将 action_cache 的变更同步回 state
        self.state_set("filter_action_cache", action_cache)

        if action_cache.get("filter_selected") and action_cache.get(
            "filter_ok_scrolled"
        ):
            no_target_box = self._find_text_box(
                page_info.get("ocr_results", []),
                get_text_patterns("card_filter_no_target"),
                exact=False,
            )
            if no_target_box:
                logger.info("筛选界面提示无对象卡牌，任务直接结束")
                self.complete()
                return ActionResult.ok(wait=0.5)
            return self._mark_filter_applied(result)

        return result

    def _handle_card_sort_panel(self, page_info: dict) -> ActionResult:
        ocr_results = page_info.get("ocr_results", [])
        target_box = self._find_text_box(
            ocr_results, get_text_patterns("card_sort_by_acquired"), exact=False
        )

        arrow_up = self.page_detector.find_template("icon_arrow_up", threshold=0.8)
        if target_box and arrow_up and self._is_arrow_up_for_sort(target_box, arrow_up):
            self.mark_action_done("sort_ready")
            close_result = click_close(
                self.adb,
                self.page_detector,
                ocr_results,
                get_text_patterns("text_x"),
            ) or ActionResult.ok(wait=0.5)
            time.sleep(0.5)
            center = (self.adb.center_x(), self.adb.center_y())
            pinch_in(self.adb, center=center, scale=0.12, steps=8, wait=0.5)
            logger.info("关闭排序面板后执行一次缩小")
            return close_result

        if target_box is None:
            logger.debug("未识别到排序目标文本，等待重试")
            return ActionResult.ok(wait=0.5)

        if arrow_up and not self._is_arrow_up_for_sort(target_box, arrow_up):
            logger.debug("当前排序箭头不在目标行，尝试切换排序")

        if not self.is_action_done("sort_clicked"):
            result = tap_text(
                self.adb,
                ocr_results,
                get_text_patterns("card_sort_by_acquired"),
                exact=False,
                wait=1.0,
            )
            if result:
                self.mark_action_done("sort_clicked")
                return result
            logger.debug("未找到排序文本，等待重试")
            return ActionResult.ok(wait=0.5)

        return ActionResult.ok(wait=0.8)

    def _tap_sort_button(self) -> ActionResult:
        tap_x = self.adb.scaled_x(BASE_SORT_BTN_X)
        tap_y = self.adb.scaled_y(BASE_SORT_BTN_Y)
        return tap(self.adb, tap_x, tap_y, wait=1.0)

    def _scan_and_scroll(self, page_info: dict) -> ActionResult:
        ocr_results = page_info.get("ocr_results", [])
        signature = self._build_signature(ocr_results)
        if self.state_get("last_signature") is None:
            self.state_set("last_signature", signature)

        detect_signature = self._scan_current_page()
        if int(self.state_get("consecutive_all_owned", 0)) >= 3:
            logger.info("连续三次识别卡牌均已入库，提前结束扫描")
            self._flush_pending_cards()
            self.complete()
            return ActionResult.ok(wait=1.0)
        if detect_signature:
            if self.state_get(
                "last_detect_signature"
            ) and detect_signature == self.state_get("last_detect_signature"):
                logger.info("检测结果未变化，认为到达列表底部")
                self._flush_pending_cards()
                self.complete()
                return ActionResult.ok(wait=1.0)
            self.state_set("last_detect_signature", detect_signature)
        start, end = scroll_points(
            self.adb, base_distance_y=BASE_SCAN_SCROLL_DISTANCE_Y, direction="up"
        )
        swipe(self.adb, start, end, steps=SWIPE_STEPS_SCROLL, wait=0.8)
        _, next_ocr = self.page_detector.capture()
        next_signature = self._build_signature(next_ocr)

        if next_signature == self.state_get("last_signature"):
            logger.info("已到达列表底部，切换下一个稀有度")
            self._flush_pending_cards()
            self.complete()
            return ActionResult.ok(wait=1.0)

        self.state_set("last_signature", next_signature)
        return ActionResult.ok(wait=0.5)

    def _scan_current_page(self) -> Optional[str]:
        if not self._account_card_repo or not self._card_repo:
            return None
        if self.account.id is None:
            return None

        detected = self.card_recognizer.scan(
            resolve_name=lambda set_code, card_number: resolve_card_name(
                self._card_repo, set_code, card_number
            ),
        )
        if not detected:
            self.state_set("consecutive_all_owned", 0)
            return None

        written = 0
        skipped_not_high = 0
        skipped_missing = 0
        skipped_no_set = 0
        signature_items = []
        all_in_db = True
        pending_cards = cast(
            dict[int, tuple[float, float]], self.state_get("pending_cards", {})
        )
        pending_order = cast(list[int], self.state_get("pending_order", []))
        for item in detected:
            if not item.set_code:
                skipped_no_set += 1
                all_in_db = False
                continue
            card = self._card_repo.get_card_by_set_and_number(
                item.set_code, item.card_number
            )
            if not card:
                skipped_missing += 1
                all_in_db = False
                continue
            signature_items.append(f"{item.set_code}:{item.card_number}")
            if card.rarity not in HIGH_RARITY_TARGETS:
                skipped_not_high += 1
                all_in_db = False
                continue
            if card.id is None:
                all_in_db = False
                continue
            if self._account_card_repo.get(self.account.id, card.id) is None:
                all_in_db = False
            conf = float(item.confidence)
            sim = float(item.similarity)
            if card.id not in pending_cards:
                pending_order.append(card.id)
                pending_cards[card.id] = (conf, sim)
            else:
                prev_conf, prev_sim = pending_cards[card.id]
                # 以最高相似度为准，同时保留对应置信度
                if sim > prev_sim:
                    pending_cards[card.id] = (conf, sim)
            written += 1

        self.state_set("pending_cards", pending_cards)
        self.state_set("pending_order", pending_order)

        # 注意：该逻辑依赖“按获得顺序最新到旧”的排序，若变更排序需重新评估
        if all_in_db:
            self.state_set(
                "consecutive_all_owned",
                int(self.state_get("consecutive_all_owned", 0)) + 1,
            )
        else:
            self.state_set("consecutive_all_owned", 0)

        logger.info("已写入高稀有度卡牌: %s 张", written)
        logger.info(
            "跳过统计: 无set=%s, 未入库=%s, 非高稀有度=%s",
            skipped_no_set,
            skipped_missing,
            skipped_not_high,
        )
        if not signature_items:
            return None
        return "|".join(sorted(signature_items))

    def _flush_pending_cards(self):
        if not self._account_card_repo:
            return
        if self.account.id is None:
            return
        pending_cards = cast(
            dict[int, tuple[float, float]], self.state_get("pending_cards", {})
        )
        pending_order = cast(list[int], self.state_get("pending_order", []))
        if not pending_cards:
            return

        logger.info("开始批量写入卡牌，共 %s 张", len(pending_cards))
        for card_id in reversed(pending_order):
            conf, sim = pending_cards[card_id]
            existing = self._account_card_repo.get(self.account.id, card_id)
            # 收集任务只用于“建立拥有关系”，不应覆盖真实库存数量：
            # - 新纪录：count=1
            # - 已存在：保持原 count 不变，仅刷新识别置信度
            count = int(existing.count) if existing is not None else 1
            self._account_card_repo.upsert(
                account_id=self.account.id,
                card_id=card_id,
                count=count,
                yolo_conf=conf,
                hash_similarity=sim,
            )
        logger.info("批量写入完成")

    def _mark_filter_applied(self, result: ActionResult) -> ActionResult:
        self.mark_action_done("filter_applied")
        filter_action_cache = cast(
            dict[str, bool], self.state_get("filter_action_cache", {})
        )
        filter_action_cache.pop("filter_scrolled", None)
        filter_action_cache.pop("filter_cleared", None)
        filter_action_cache.pop("filter_selected", None)
        filter_action_cache.pop("filter_ok_scrolled", None)
        self.state_set("filter_action_cache", filter_action_cache)
        return result

    @staticmethod
    def _build_signature(ocr_results: list[dict]) -> str:
        texts = [item.get("text", "").strip() for item in ocr_results]
        return "|".join(sorted(texts))

    @staticmethod
    def _find_text_box(
        ocr_results: list[dict], patterns: list[str], exact: bool = False
    ) -> Optional[tuple[int, int, int, int]]:
        for pattern in patterns:
            pattern_norm = "".join(pattern.lower().split())
            for item in ocr_results:
                text = "".join(item.get("text", "").lower().split())
                if exact:
                    matched = pattern_norm == text
                else:
                    matched = pattern_norm in text
                if matched:
                    box = item.get("box")
                    if box and len(box) == 4:
                        return tuple(box)
        return None

    def _is_arrow_up_for_sort(
        self,
        target_box: tuple[int, int, int, int],
        arrow_box: tuple[int, int, int, int],
    ) -> bool:
        target_cy = (target_box[1] + target_box[3]) / 2
        arrow_cy = (arrow_box[1] + arrow_box[3]) / 2
        row_tol = self.adb.scaled_y(BASE_SORT_ROW_TOL)
        if abs(target_cy - arrow_cy) > row_tol:
            return False
        return arrow_box[0] >= target_box[0]
