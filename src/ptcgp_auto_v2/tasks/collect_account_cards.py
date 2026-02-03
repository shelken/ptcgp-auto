# -*- coding: utf-8 -*-
"""
收集账号高稀有度卡牌信息任务

流程：主页 -> 卡牌页 -> 筛选高稀有度 -> 排序为最新 -> 识别卡牌 -> 记录数据
"""

import logging
from enum import Enum, auto
from typing import Optional

from ptcgp_auto_v2.config.constants import HIGH_RARITY_TARGETS
from ptcgp_auto_v2.config.rarity_icons import (
    RARITY_CODE_REVERSE,
    RARITY_GROUP_DEFAULTS,
    RARITY_ICON_TEMPLATES,
)
from ptcgp_auto_v2.core.task_base import (
    ActionResult,
    ResetType,
    Task,
    TaskRegistry,
)
from ptcgp_auto_v2.infra.card_hash_manager import get_card_hash_manager
from ptcgp_auto_v2.infra.icon_group_detector import (
    IconGroupDetector,
    find_group_by_rarity,
)
from ptcgp_auto_v2.infra.model_manager import get_model_manager
from ptcgp_auto_v2.infra.yolo_card_recognizer import YoloCardRecognizer
from ptcgp_auto_v2.locales import get_text_patterns
from ptcgp_auto_v2.utils.gesture import (
    click_close,
    quick_tap,
    swipe_up,
    tap_ok,
    tap_template,
    tap_text,
    tap_text_exact,
)

logger = logging.getLogger(__name__)


# ============================================================
# 常量定义（基于 1080x1920 基准分辨率）
# ============================================================

BASE_FILTER_ROI_X1 = 80
BASE_FILTER_ROI_X2 = 1000
BASE_FILTER_ROI_HEIGHT = 520
BASE_FILTER_SCROLL_RATIO = 0.1
FILTER_SCROLL_WAIT = 1.2
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
class CollectAccountCardsTask(Task):
    """收集当前账号高稀有度卡牌信息"""

    task_type = "collect_account_cards"
    reset_type = ResetType.DAILY
    max_iterations = 200
    max_unknown_pages = 20
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

        self._action_cache: dict[str, bool] = {}
        self._completed = False
        self._skipped = False
        self._skip_reason: Optional[str] = None
        self._phase = CollectPhase.ENTER
        self._last_signature: Optional[str] = None
        self._last_detect_signature: Optional[str] = None
        self._pending_cards: list[tuple[int, float, float]] = []
        self._pending_seen: set[int] = set()

        self._account_card_repo = None
        self._card_repo = None

    def _is_action_done(self, key: str) -> bool:
        return self._action_cache.get(key, False)

    def _mark_action_done(self, key: str):
        self._action_cache[key] = True

    def _reset_action_cache(self):
        self._action_cache.clear()

    def on_start(self):
        from ptcgp_auto_v2.db.repositories import AccountCardRepository, CardRepository

        self._account_card_repo = AccountCardRepository()
        self._card_repo = CardRepository()

        self._action_cache.clear()
        self._completed = False
        self._skipped = False
        self._skip_reason = None
        self._phase = CollectPhase.ENTER
        self._last_signature = None
        self._last_detect_signature = None
        self._pending_cards = []
        self._pending_seen = set()

        if self.account.id is None:
            logger.error("账号 ID 为空，无法执行收集任务")
            self._skipped = True
            self._skip_reason = "账号 ID 为空"
            self._completed = True

    def is_completed(self) -> bool:
        return self._completed or self._skipped

    def was_skipped(self) -> bool:
        return self._skipped

    def handle_page(self, page_name: str, page_info: dict) -> ActionResult:
        handlers = {
            "game_home_main": self._handle_home,
            "card_entry_icon": self._handle_card_entry,
            "card_page_own": self._handle_card_page,
            "card_filter_panel": self._handle_filter_panel,
            "card_sort_panel": self._handle_sort_panel,
        }
        handler = handlers.get(page_name)
        if handler:
            return handler(page_info)
        return ActionResult.ok(wait=1.0)

    def handle_unknown_page(self, page_info) -> ActionResult:
        logger.debug("未知页面，等待后重试")
        return ActionResult.wait(0.5)

    def _handle_home(self, page_info: dict) -> ActionResult:
        return self._handle_card_entry(page_info)

    def _handle_card_entry(self, page_info: dict) -> ActionResult:
        result = tap_template(
            self.adb, self.page_detector, "icon_bottom_card", wait=1.0
        )
        return result or ActionResult.ok(wait=1.0)

    def _handle_card_page(self, page_info: dict) -> ActionResult:
        logger.info("进入卡牌页处理，当前阶段: %s", self._phase.name)
        if not self._is_action_done("filter_applied"):
            self._phase = CollectPhase.FILTER
            result = tap_template(self.adb, self.page_detector, "icon_search", wait=1.0)
            if result:
                return result
            fallback = self.page_detector.find_template("icon_search", threshold=0.6)
            if fallback:
                self.adb.tap_center(fallback)
                return ActionResult.ok(wait=1.0)
            return ActionResult.ok(wait=1.0)

        if not self._is_action_done("sort_ready"):
            self._phase = CollectPhase.SORT
            return self._tap_sort_button()

        self._phase = CollectPhase.SCAN
        return self._scan_and_scroll(page_info)

    def _handle_filter_panel(self, page_info: dict) -> ActionResult:
        ocr_results = page_info.get("ocr_results", [])

        no_target_box = self._find_text_box(
            ocr_results, get_text_patterns("card_filter_no_target"), exact=False
        )
        if no_target_box:
            logger.info("筛选界面提示无对象卡牌，任务直接结束")
            self._completed = True
            return ActionResult.ok(wait=0.5)

        if not self._is_action_done("filter_cleared"):
            result = tap_text_exact(
                self.adb,
                ocr_results,
                get_text_patterns("card_filter_clear"),
                wait=0.5,
            )
            if result:
                self._mark_action_done("filter_cleared")
                return result
            return ActionResult.ok(wait=0.5)

        if not self._is_action_done("filter_scrolled"):
            swipe_up(self.adb, ratio=BASE_FILTER_SCROLL_RATIO, wait=FILTER_SCROLL_WAIT)
            self._mark_action_done("filter_scrolled")
            return ActionResult.ok(wait=FILTER_SCROLL_WAIT)

        if not self._is_action_done("filter_selected"):
            result = self._select_high_rarities(page_info)
            if result:
                self._mark_action_done("filter_selected")
                ok_result = tap_ok(self.adb, ocr_results, wait=1.0)
                if ok_result:
                    return self._mark_filter_applied(ok_result)
                if not self._is_action_done("filter_ok_scrolled"):
                    self.adb.swipe_down(ratio=0.08)
                    self._mark_action_done("filter_ok_scrolled")
                    return ActionResult.ok(wait=0.8)
                return result
            return ActionResult.ok(wait=0.5)

        result = tap_ok(self.adb, ocr_results, wait=1.0)
        if result:
            return self._mark_filter_applied(result)

        return ActionResult.ok(wait=0.5)

    def _handle_sort_panel(self, page_info: dict) -> ActionResult:
        ocr_results = page_info.get("ocr_results", [])
        target_box = self._find_text_box(
            ocr_results, get_text_patterns("card_sort_by_acquired"), exact=False
        )

        arrow_up = self.page_detector.find_template("icon_arrow_up", threshold=0.8)
        if target_box and arrow_up and self._is_arrow_up_for_sort(target_box, arrow_up):
            self._mark_action_done("sort_ready")
            return click_close(
                self.adb,
                self.page_detector,
                ocr_results,
                get_text_patterns("text_x"),
            ) or ActionResult.ok(wait=0.5)

        if target_box is None:
            logger.debug("未识别到排序目标文本，等待重试")
            return ActionResult.ok(wait=0.5)

        if arrow_up and not self._is_arrow_up_for_sort(target_box, arrow_up):
            logger.debug("当前排序箭头不在目标行，尝试切换排序")

        if not self._is_action_done("sort_clicked"):
            result = tap_text(
                self.adb,
                ocr_results,
                get_text_patterns("card_sort_by_acquired"),
                exact=False,
                wait=1.0,
            )
            if result:
                self._mark_action_done("sort_clicked")
                return result
            logger.debug("未找到排序文本，等待重试")
            return ActionResult.ok(wait=0.5)

        return ActionResult.ok(wait=0.8)

    def _tap_sort_button(self) -> ActionResult:
        tap_x = self.adb.scaled_x(BASE_SORT_BTN_X)
        tap_y = self.adb.scaled_y(BASE_SORT_BTN_Y)
        self.adb.tap(tap_x, tap_y)
        return ActionResult.ok(wait=1.0)

    def _select_high_rarities(self, page_info: dict) -> Optional[ActionResult]:
        screenshot, ocr_results = self.page_detector.get_last_page_context()
        if screenshot is None:
            screenshot, ocr_results = self.page_detector.capture()
            if screenshot is None:
                return None

        title_box = self._find_text_box(
            ocr_results, get_text_patterns("card_filter_title"), exact=True
        )
        if not title_box:
            return None

        roi_x1 = self.adb.scaled_x(BASE_FILTER_ROI_X1)
        roi_x2 = self.adb.scaled_x(BASE_FILTER_ROI_X2)
        roi_y1 = title_box[1]
        roi_y2 = title_box[3] + self.adb.scaled_y(BASE_FILTER_ROI_HEIGHT)
        roi = (roi_x1, roi_y1, roi_x2, min(roi_y2, self.adb.screen_height))

        hits = self.icon_detector.detect_icons(
            screenshot=screenshot,
            template_paths=RARITY_ICON_TEMPLATES,
            roi=roi,
            threshold=RARITY_GROUP_DEFAULTS["threshold"],
            nms_iou=RARITY_GROUP_DEFAULTS["nms_iou"],
            screen_width=self.adb.screen_width,
        )

        row_tol = self.adb.scaled_y(RARITY_GROUP_DEFAULTS["row_tol_px"])
        gap = self.adb.scaled_x(RARITY_GROUP_DEFAULTS["gap_px"])
        groups = self.icon_detector.group_hits(
            hits,
            row_tol=row_tol,
            gap=gap,
            min_count=RARITY_GROUP_DEFAULTS["min_count"],
        )

        clicked = False
        visited = set()
        for rarity_code in HIGH_RARITY_TARGETS:
            pattern = RARITY_CODE_REVERSE.get(rarity_code)
            if not pattern:
                continue
            if pattern in visited:
                continue
            visited.add(pattern)
            group = find_group_by_rarity(rarity_code, groups, RARITY_CODE_REVERSE)
            if not group:
                logger.debug("未找到稀有度分组: %s", rarity_code)
                continue
            self.adb.tap(int(group.center[0]), int(group.center[1]))
            logger.info("已选择稀有度: %s", rarity_code)
            clicked = True

        return ActionResult.ok(wait=0.5) if clicked else None

    def _scan_and_scroll(self, page_info: dict) -> ActionResult:
        ocr_results = page_info.get("ocr_results", [])
        signature = self._build_signature(ocr_results)
        if self._last_signature is None:
            self._last_signature = signature

        detect_signature = self._scan_current_page()
        if detect_signature:
            if (
                self._last_detect_signature
                and detect_signature == self._last_detect_signature
            ):
                logger.info("检测结果未变化，认为到达列表底部")
                self._flush_pending_cards()
                self._completed = True
                return ActionResult.ok(wait=1.0)
            self._last_detect_signature = detect_signature
        swipe_up(self.adb, ratio=0.26, wait=0.8)
        _, next_ocr = self.page_detector.capture()
        next_signature = self._build_signature(next_ocr)

        if next_signature == self._last_signature:
            logger.info("已到达列表底部，切换下一个稀有度")
            self._flush_pending_cards()
            self._completed = True
            return ActionResult.ok(wait=1.0)

        self._last_signature = next_signature
        return ActionResult.ok(wait=0.5)

    def _scan_current_page(self) -> Optional[str]:
        if not self._account_card_repo or not self._card_repo:
            return None
        if self.account.id is None:
            return None

        detected, unmatched = self.card_recognizer.scan_with_debug()
        total_detected = len(detected) + len(unmatched)
        if total_detected == 0:
            logger.debug("未识别到卡牌或模型未就绪")
            return None

        logger.info("====== 识别到 %s/%s 张卡牌 ======", len(detected), total_detected)
        for item in detected:
            logger.info(
                "  - %s%s (Conf: %.2f, Sim: %.2f)",
                item.set_code or "?",
                item.card_number,
                item.confidence,
                item.similarity,
            )

        if unmatched:
            logger.info("====== 未匹配 %s 张卡牌 ======", len(unmatched))
            for idx, item in enumerate(unmatched, start=1):
                logger.info(
                    "  - #%s best=%s/%s (Conf: %.2f, Sim: %.2f)",
                    idx,
                    item.get("best_set_code") or "unknown",
                    item.get("best_card_number")
                    if item.get("best_card_number") is not None
                    else "unknown",
                    float(item.get("confidence") or 0.0),
                    float(item.get("similarity") or 0.0),
                )

        written = 0
        skipped_not_high = 0
        skipped_missing = 0
        skipped_no_set = 0
        signature_items = []
        for item in detected:
            if not item.set_code:
                skipped_no_set += 1
                continue
            card = self._card_repo.get_card_by_set_and_number(
                item.set_code, item.card_number
            )
            if not card:
                skipped_missing += 1
                continue
            signature_items.append(f"{item.set_code}:{item.card_number}")
            if card.rarity not in HIGH_RARITY_TARGETS:
                skipped_not_high += 1
                continue
            if card.id is None:
                continue
            if card.id in self._pending_seen:
                continue
            self._pending_seen.add(card.id)
            self._pending_cards.append(
                (card.id, float(item.confidence), float(item.similarity))
            )
            written += 1

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
        if not self._pending_cards:
            return

        logger.info("开始批量写入卡牌，共 %s 张", len(self._pending_cards))
        for card_id, conf, sim in reversed(self._pending_cards):
            self._account_card_repo.upsert(
                account_id=self.account.id,
                card_id=card_id,
                count=1,
                yolo_conf=conf,
                hash_similarity=sim,
            )
        logger.info("批量写入完成")

    def _mark_filter_applied(self, result: ActionResult) -> ActionResult:
        self._mark_action_done("filter_applied")
        self._action_cache.pop("filter_scrolled", None)
        self._action_cache.pop("filter_cleared", None)
        self._action_cache.pop("filter_selected", None)
        self._action_cache.pop("filter_ok_scrolled", None)
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
        return arrow_box[0] >= target_box[2]
