# -*- coding: utf-8 -*-
"""
每日送卡任务。

初版策略：
1. 自动配对系统内账号（稳定关系，缺失时增量补齐）
2. 固定送出 A1-153（嘎啦嘎啦）
3. 成功后记录流水并同步 account_cards 剩余数量
"""

import logging
from datetime import datetime, timedelta
from typing import Optional

from ptcgp_auto_v2.core.task_base import ActionResult, ResetType, Task, TaskRegistry
from ptcgp_auto_v2.db.repositories import (
    AccountCardRepository,
    AccountRepository,
    CardRepository,
)
from ptcgp_auto_v2.hooks import (
    ClaimGiftsPreHook,
    FriendPreHook,
    SendCardWakeTargetPostHook,
)
from ptcgp_auto_v2.infra.card_hash_manager import get_card_hash_manager
from ptcgp_auto_v2.infra.model_manager import get_model_manager
from ptcgp_auto_v2.infra.yolo_card_recognizer import YoloCardRecognizer
from ptcgp_auto_v2.locales import get_text_patterns
from ptcgp_auto_v2.services import GiftPairingService, GiftRecordService
from ptcgp_auto_v2.tasks.utils.friend_id_utils import extract_friend_id_from_text
from ptcgp_auto_v2.tasks.utils.pack_opening_flow import swipe_card_register
from ptcgp_auto_v2.tasks.utils.send_card_helpers import (
    build_ocr_signature,
    find_send_box_near_anchor,
    find_send_button_for_target,
    find_target_search_plus_box,
)
from ptcgp_auto_v2.utils.gesture import (
    clear_text,
    click_close,
    input_text,
    is_text_visible,
    quick_tap,
    scroll_points,
    swipe,
    tap,
    tap_box,
    tap_community_icon,
    tap_ok,
    tap_template,
    tap_text_exact,
)

logger = logging.getLogger(__name__)

# ============================================================
# 常量定义（基于 1080x1920）
# ============================================================

FIXED_CARD_SET_CODE = "A1"
FIXED_CARD_NUMBER = 153

BASE_FRIEND_SCROLL_DISTANCE_Y = 520
BASE_CARD_SCROLL_DISTANCE_Y = 500
# 说明：好友列表行高与 OCR 抖动会造成约 130+ 的同一行偏差，
# 轻度放宽到 150，避免误判同时不跨到下一行。
BASE_FRIEND_ROW_THRESHOLD_Y = 150

MAX_FRIEND_SCROLL_ROUNDS = 8
MAX_FRIEND_STABLE_ROUNDS = 3
MAX_CARD_STABLE_ROUNDS = 3
MAX_FILTER_MODAL_STAY_ROUNDS = 2
MAX_FRIEND_PROFILE_READ_ROUNDS = 3


def _build_send_card_pages() -> list[dict]:
    """构建送卡任务页面规则。"""
    return [
        {
            "name": "home_with_community_icon",
            "templates": ["icon_community"],
            "priority": 10,
        },
        {
            "name": "game_home_main",
            "identifiers": get_text_patterns("game_home_main"),
            "match_all": True,
            "priority": 20,
        },
        {
            "name": "community_page",
            "identifiers": get_text_patterns("community_page"),
            "match_all": True,
            "priority": 40,
        },
        {
            "name": "gift_page_main",
            "identifiers": get_text_patterns("gift_page_main"),
            "match_all": True,
            "priority": 50,
        },
        {
            "name": "gift_choose_friend",
            "identifiers": get_text_patterns("gift_choose_friend_title"),
            "priority": 60,
        },
        {
            "name": "gift_friend_profile",
            "identifiers": get_text_patterns("gift_friend_profile"),
            "priority": 65,
        },
        {
            "name": "gift_select_card",
            "identifiers": get_text_patterns("gift_select_card_title"),
            "priority": 70,
        },
        {
            "name": "gift_filter_modal",
            "identifiers": get_text_patterns("gift_filter_modal_title"),
            "match_all": True,
            "priority": 71,
        },
        {
            "name": "gift_target_page",
            "identifiers": get_text_patterns("gift_target_page"),
            "priority": 80,
        },
        {
            "name": "gift_confirm_popup",
            "identifiers": get_text_patterns("gift_confirm_send_popup"),
            "priority": 90,
        },
        {
            "name": "gift_confirm_last_popup",
            "identifiers": get_text_patterns("gift_confirm_last_card_popup"),
            "priority": 91,
        },
        {
            "name": "gift_swipe_page",
            "identifiers": get_text_patterns("gift_swipe_to_send"),
            "priority": 95,
        },
    ]


@TaskRegistry.register("send_card_daily")
class SendCardDailyTask(Task):
    """每日送卡任务。"""

    task_type = "send_card_daily"
    reset_type = ResetType.INTERVAL
    max_iterations = 180
    max_unknown_pages = 20
    pages = _build_send_card_pages()

    def __init__(self, adb, recognizer, page_detector):
        super().__init__(adb, recognizer, page_detector)
        self.card_recognizer = YoloCardRecognizer(
            adb=adb,
            model_manager=get_model_manager(),
            hash_manager=get_card_hash_manager(),
        )
        self._action_cache: dict[str, bool] = {}
        self._last_page_name: Optional[str] = None
        self._prev_page_name: Optional[str] = None

        self._completed = False
        self._complete_reason: Optional[str] = None

        self._target_friend_id: Optional[str] = None
        self._target_account_id: Optional[int] = None
        self._target_nickname: Optional[str] = None
        self._fixed_card_id: Optional[int] = None

        self._record = None

        self._friend_scroll_rounds = 0
        self._friend_stable_rounds = 0
        self._card_stable_rounds = 0
        self._last_friend_signature: Optional[str] = None
        self._last_card_signature: Optional[str] = None

        self._before_count: Optional[int] = None
        self._after_count: Optional[int] = None
        self._gift_sent_success = False
        self._filter_applied = False
        self._filter_opened = False
        self._filter_modal_stay_rounds = 0

        self._target_friend_verified = False
        self._verified_row_anchor_y: Optional[int] = None
        self._friend_profile_read_rounds = 0
        self._failed_plus_rows: set[int] = set()

        self._skip_reason: Optional[str] = None

    def was_skipped(self) -> bool:
        """任务是否被跳过（不更新 last_completed_at）。"""
        return self._skip_reason is not None

    def _is_action_done(self, key: str) -> bool:
        """检查动作缓存。"""
        return self._action_cache.get(key, False)

    def _mark_action_done(self, key: str):
        """标记动作完成。"""
        self._action_cache[key] = True

    def _reset_action_cache(self):
        """重置页面动作缓存。"""
        self._action_cache.clear()

    def on_start(self):
        """任务启动初始化。"""
        self._completed = False
        self._complete_reason = None
        self._friend_scroll_rounds = 0
        self._friend_stable_rounds = 0
        self._card_stable_rounds = 0
        self._last_friend_signature = None
        self._last_card_signature = None
        self._before_count = None
        self._after_count = None
        self._gift_sent_success = False
        self._fixed_card_id = None
        self._filter_applied = False
        self._filter_opened = False
        self._filter_modal_stay_rounds = 0

        self._target_friend_verified = False
        self._verified_row_anchor_y = None
        self._friend_profile_read_rounds = 0
        self._failed_plus_rows: set[int] = set()
        self._prev_page_name = None
        self._reset_action_cache()

        if self.account.id is None:
            self._complete_reason = "账号ID为空"
            self._completed = True
            return

        if not GiftPairingService.is_account_past_cooldown(self.account.created_at):
            if self._is_same_day_pending_cooldown(self.account.created_at):
                self._skip_reason = "账号未过14天冷冻期（同日待到期）"
                return
            self._complete_reason = "账号未过14天冷冻期"
            self._completed = True
            return

        pair = GiftPairingService.ensure_pairs_for_account(self.account.id)
        if pair is None:
            self._skip_reason = "无可用送卡目标"
            return

        self._target_friend_id = pair.target_friend_id
        self._target_account_id = pair.target_account_id
        if pair.target_account_id is not None:
            target_account = AccountRepository().get_by_id(pair.target_account_id)
            if target_account:
                self._target_nickname = target_account.nickname

        if not self._target_friend_id:
            self._complete_reason = "目标 friend_id 为空"
            self._completed = True
            return

        fixed_card = CardRepository().get_card_by_set_and_number(
            FIXED_CARD_SET_CODE,
            FIXED_CARD_NUMBER,
        )
        self._fixed_card_id = fixed_card.id if fixed_card else None

        if GiftRecordService.is_daily_success(self.account.id, self._target_friend_id):
            self._complete_reason = "今日已送卡成功"
            self._completed = True
            return

        self._record = GiftRecordService.ensure_daily_record(
            account_id=self.account.id,
            target_friend_id=self._target_friend_id,
            target_account_id=self._target_account_id,
            card_set_code=FIXED_CARD_SET_CODE,
            card_number=FIXED_CARD_NUMBER,
        )

        self._maybe_complete_for_pair_ordering()

    def _is_same_day_pending_cooldown(self, created_at: Optional[datetime]) -> bool:
        """判断账号是否同日待过冷冻期（未到时间但到期日与今天相同）。"""
        if created_at is None:
            return False
        cooldown_days = getattr(GiftPairingService, "COOLDOWN_DAYS", 14)
        if not isinstance(cooldown_days, int):
            cooldown_days = 14
        cooldown_at = created_at + timedelta(days=cooldown_days)
        now = datetime.now()
        return now < cooldown_at and now.date() == cooldown_at.date()

    def is_completed(self) -> bool:
        """任务是否完成。"""
        return self._completed

    def get_pre_hooks(self) -> list:
        """前置 Hook：确保好友关系存在。"""
        if self._completed or not self._target_friend_id:
            return []
        return [
            ClaimGiftsPreHook(),
            FriendPreHook(
                target_friend_id=self._target_friend_id,
                target_account_id=self._target_account_id,
            ),
        ]

    def get_post_hooks(self) -> list:
        """后置 Hook：送卡成功后尝试唤醒目标账号回送。"""
        return [SendCardWakeTargetPostHook()]

    def handle_page(self, page_name: str, page_info: dict) -> ActionResult:
        """页面分发处理。"""
        # 极简方案：点击加号等详情页加载时，吞掉其他页面匹配
        if (
            self._is_action_done("friend_plus_clicked")
            and not self._target_friend_verified
            and page_name not in ("gift_friend_profile", "gift_choose_friend")
        ):
            return ActionResult.wait(1.5)

        previous_page_name = self._last_page_name
        if page_name != self._last_page_name:
            self._prev_page_name = previous_page_name
            self._last_page_name = page_name
            self._reset_action_cache()

        # 兜底：筛选弹窗返回选卡页时，视为筛选流程已应用。
        if (
            page_name == "gift_select_card"
            and self._prev_page_name == "gift_filter_modal"
            and self._filter_opened
        ):
            self._filter_applied = True
            self._filter_modal_stay_rounds = 0

        handlers = {
            "home_with_community_icon": self._handle_home,
            "game_home_main": self._handle_home,
            "community_page": self._handle_community,
            "gift_page_main": self._handle_gift_page_main,
            "gift_choose_friend": self._handle_choose_friend,
            "gift_friend_profile": self._handle_friend_profile,
            "gift_select_card": self._handle_select_card,
            "gift_filter_modal": self._handle_filter_modal,
            "gift_target_page": self._handle_target_page,
            "gift_confirm_popup": self._handle_confirm_popup,
            "gift_confirm_last_popup": self._handle_confirm_last_popup,
            "gift_swipe_page": self._handle_swipe_page,
        }
        handler = handlers.get(page_name)
        if handler:
            return handler(page_info)
        return ActionResult.wait(0.8)

    def _fail(self, error_code: str, message: str) -> ActionResult:
        """统一失败处理。"""
        logger.warning("send_card_daily 失败: %s - %s", error_code, message)
        if self._record:
            GiftRecordService.update_status(
                self._record,
                status="failed",
                error_code=error_code,
                error_message=message,
            )
        return ActionResult.fail(f"{error_code}: {message}")

    def _complete_without_send(
        self,
        complete_reason: str,
        record_status: str,
        error_code: Optional[str] = None,
    ) -> ActionResult:
        """在无需继续尝试时以完成态收敛任务。"""
        self._complete_reason = complete_reason
        self._completed = True
        logger.info("send_card_daily 完成收敛: %s", complete_reason)
        if self._record:
            GiftRecordService.update_status(
                self._record,
                status=record_status,
                error_code=error_code,
                error_message=complete_reason,
            )
        return ActionResult.ok(wait=0.3)

    def _skip_without_send(
        self,
        skip_reason: str,
        record_status: Optional[str] = None,
        error_code: Optional[str] = None,
    ) -> ActionResult:
        """在无需继续尝试时以跳过态收敛任务，同时保留必要状态落库。"""
        self._skip_reason = skip_reason
        logger.info("send_card_daily 跳过收敛: %s", skip_reason)
        if self._record and record_status:
            GiftRecordService.update_status(
                self._record,
                status=record_status,
                error_code=error_code,
                error_message=skip_reason,
            )
        return ActionResult.ok(wait=0.3)

    def _handle_home(self, page_info: dict) -> ActionResult:
        """主页点击社群入口。"""
        if self._completed:
            return ActionResult.ok(wait=0.5)
        return tap_community_icon(self.adb, self.page_detector, wait=1.0)

    def _handle_community(self, page_info: dict) -> ActionResult:
        """社群页面点击分送入口。"""
        ocr_results = page_info.get("ocr_results", [])
        # 防止教程
        quick_tap(self.adb)
        result = tap_text_exact(
            self.adb,
            ocr_results,
            get_text_patterns("gift_tab_send"),
            wait=1.0,
        )
        return result or ActionResult.wait(0.8)

    def _handle_gift_page_main(self, page_info: dict) -> ActionResult:
        """分送主页面点击下方分送按钮。"""
        ocr_results = page_info.get("ocr_results", [])
        candidates: list[tuple[int, tuple[int, int, int, int]]] = []
        for item in ocr_results:
            text = "".join(str(item.get("text", "")).lower().split())
            if text not in {
                "".join(t.lower().split()) for t in get_text_patterns("gift_tab_send")
            }:
                continue
            box = item.get("box")
            if not box:
                continue
            center_y = (box[1] + box[3]) // 2
            if center_y <= self.adb.center_y():
                continue
            candidates.append((center_y, tuple(box)))

        if not candidates:
            return ActionResult.wait(0.8)

        candidates.sort(key=lambda item: item[0])
        return tap_box(self.adb, candidates[0][1], wait=1.0)

    def _handle_choose_friend(self, page_info: dict) -> ActionResult:
        """好友选择页：先点加号核验 friend_id，再点击对应分送。"""
        ocr_results = page_info.get("ocr_results", [])

        if is_text_visible(
            ocr_results,
            get_text_patterns("gift_choose_friend_empty"),
            exact=False,
        ):
            return self._skip_without_send(
                skip_reason="好友列表为空，无法分送卡牌",
                record_status="completed_no_target",
                error_code="NO_FRIENDS",
            )

        friend_signature = build_ocr_signature(ocr_results)
        if friend_signature == self._last_friend_signature:
            self._friend_stable_rounds += 1
        else:
            self._friend_stable_rounds = 0
            self._last_friend_signature = friend_signature

        # 第一阶段：必须先通过 icon_search_plus 进入详情页校验 friend_id。
        if not self._target_friend_verified:
            plus_box = self._find_target_search_plus_box(ocr_results)
            if plus_box:
                self._verified_row_anchor_y = (plus_box[1] + plus_box[3]) // 2
                self._mark_action_done("friend_plus_clicked")
                return tap_box(self.adb, plus_box, wait=3)
            return self._continue_find_target_in_friend_list()

        # 第二阶段：已核验 friend_id，回到列表后点击同一行分送。
        send_box = self._find_send_box_for_verified_target(ocr_results)
        if send_box:
            if self._record:
                GiftRecordService.update_status(self._record, status="target_found")
            self._friend_scroll_rounds = 0
            self._friend_stable_rounds = 0
            self._last_friend_signature = None
            return tap_box(self.adb, send_box, wait=1.0)

        return self._continue_find_target_in_friend_list()

    def _continue_find_target_in_friend_list(self) -> ActionResult:
        """好友列表继续查找目标（滑动或收敛）。"""
        if self._friend_stable_rounds >= MAX_FRIEND_STABLE_ROUNDS:
            return self._skip_without_send(
                skip_reason="好友列表遍历完成未找到可送目标",
                record_status="completed_no_target",
                error_code="TARGET_LIST_EXHAUSTED",
            )

        self._friend_scroll_rounds += 1
        if self._friend_scroll_rounds > MAX_FRIEND_SCROLL_ROUNDS:
            return self._complete_without_send(
                complete_reason="好友列表遍历达到上限，未定位到可送目标",
                record_status="completed_no_target",
                error_code="TARGET_NOT_FOUND",
            )

        # 滑动前清空已失败的行记录（新页面行位置重置）
        if self._failed_plus_rows:
            logger.debug("滑动前清空已失败行记录: %s", self._failed_plus_rows)
            self._failed_plus_rows.clear()

        start, end = scroll_points(
            self.adb,
            base_distance_y=BASE_FRIEND_SCROLL_DISTANCE_Y,
            direction="up",
        )
        swipe(self.adb, start, end, wait=0.9)
        return ActionResult.ok(wait=0.8)

    def _handle_friend_profile(self, page_info: dict) -> ActionResult:
        """好友详情页：提取 friend_id 核验目标后返回列表。"""
        # 已进入详情页，清除上次“已点击加号”状态，回到列表后可重新点击。
        self._action_cache.pop("friend_plus_clicked", None)
        ocr_results = page_info.get("ocr_results", [])
        extracted_friend_id: Optional[str] = None
        for item in ocr_results:
            text = str(item.get("text", ""))
            extracted_friend_id = extract_friend_id_from_text(text)
            if extracted_friend_id:
                break

        if not extracted_friend_id:
            self._friend_profile_read_rounds += 1
            if self._friend_profile_read_rounds < MAX_FRIEND_PROFILE_READ_ROUNDS:
                return ActionResult.wait(0.6)
            logger.warning("送卡详情页连续未识别到 friend_id，返回好友列表重试")
        elif self._target_friend_id and extracted_friend_id == self._target_friend_id:
            self._target_friend_verified = True
            self._mark_action_done("friend_verified")
            logger.info("好友详情核验成功：friend_id=%s", extracted_friend_id)
        else:
            self._target_friend_verified = False
            # 记录失败的行，避免重复点击同名好友
            if self._verified_row_anchor_y is not None:
                self._failed_plus_rows.add(self._verified_row_anchor_y)
            self._verified_row_anchor_y = None
            logger.info(
                "好友详情核验失败：识别到 %s，目标 %s，已记录失败行",
                extracted_friend_id,
                self._target_friend_id,
            )

        self._friend_profile_read_rounds = 0
        close_result = click_close(
            self.adb,
            self.page_detector,
            ocr_results,
            get_text_patterns("text_x"),
        )
        return close_result or ActionResult.wait(0.8)

    def _find_target_search_plus_box(
        self, ocr_results: list[dict]
    ) -> Optional[tuple[int, int, int, int]]:
        """在好友列表中查找目标昵称同一行的 icon_search_plus。"""
        if not self._target_nickname:
            logger.debug("目标昵称为空，无法执行昵称匹配")
            return None
        if not hasattr(self.page_detector, "find_all_templates"):
            logger.debug("page_detector 不支持 find_all_templates，无法定位加号")
            return None

        matches = self.page_detector.find_all_templates(
            "icon_search_plus",
            threshold=0.8,
            scale=1.0,
        )
        search_plus_boxes: list[tuple[int, int, int, int]] = []
        for match in matches:
            box = getattr(match, "box", None)
            if box and len(box) == 4:
                search_plus_boxes.append(tuple(box))

        logger.debug(
            "昵称匹配目标=%s，当前检测到 icon_search_plus=%d，已失败行=%s",
            self._target_nickname,
            len(search_plus_boxes),
            self._failed_plus_rows,
        )

        row_threshold_y = self.adb.scaled_y(BASE_FRIEND_ROW_THRESHOLD_Y)

        # 过滤掉已失败的行（比较中心点 Y 坐标）
        available_boxes = [
            box
            for box in search_plus_boxes
            if not any(
                abs((box[1] + box[3]) // 2 - failed_y) < row_threshold_y
                for failed_y in self._failed_plus_rows
            )
        ]

        matched_box = find_target_search_plus_box(
            ocr_results=ocr_results,
            target_nickname=self._target_nickname,
            search_plus_boxes=available_boxes,
            row_threshold_y=row_threshold_y,
        )
        if matched_box is None:
            logger.debug(
                "昵称匹配未命中任何加号行（过滤后剩余%d个），row_threshold_y=%s",
                len(available_boxes),
                row_threshold_y,
            )
        return matched_box

    def _find_send_box_for_verified_target(
        self, ocr_results: list[dict]
    ) -> Optional[tuple[int, int, int, int]]:
        """核验通过后按同一行锚点优先定位分送按钮。"""
        row_threshold_y = self.adb.scaled_y(BASE_FRIEND_ROW_THRESHOLD_Y)

        if self._verified_row_anchor_y is not None:
            send_box = find_send_box_near_anchor(
                ocr_results=ocr_results,
                send_text_patterns=get_text_patterns("gift_send_button"),
                anchor_y=self._verified_row_anchor_y,
                row_threshold_y=row_threshold_y,
            )
            if send_box:
                return send_box

        if not self._target_nickname:
            return None

        return find_send_button_for_target(
            ocr_results=ocr_results,
            target_nickname=self._target_nickname,
            send_text_patterns=get_text_patterns("gift_send_button"),
        )

    def _handle_select_card(self, page_info: dict) -> ActionResult:
        """选卡页面：必须先筛选，再通过扫描定位固定卡牌。"""

        if not self._filter_applied and not self._is_action_done("open_filter_clicked"):
            result = tap_template(self.adb, self.page_detector, "icon_search", wait=1.0)
            if result:
                self._filter_opened = True
                self._mark_action_done("open_filter_clicked")
                return result

        # 约束：未完成筛选前，不进行任何 OCR 选卡与滑动找卡。
        if not self._filter_applied:
            return ActionResult.wait(0.6)

        detected = self.card_recognizer.scan(
            set_code=FIXED_CARD_SET_CODE,
            debug=False,
        )
        scan_tap_result = self._tap_target_card_by_scan(detected)
        if scan_tap_result:
            if self._record:
                GiftRecordService.update_status(self._record, status="card_selected")
            return scan_tap_result

        signature = self._build_detect_signature(detected)
        if signature == self._last_card_signature:
            self._card_stable_rounds += 1
        else:
            self._card_stable_rounds = 0
            self._last_card_signature = signature

        if self._card_stable_rounds >= MAX_CARD_STABLE_ROUNDS:
            return self._complete_without_send(
                complete_reason="扫描多次未找到目标卡 A1-153，结束本次送卡任务",
                record_status="completed_no_card",
                error_code="CARD_NOT_FOUND_BY_SCAN",
            )

        start, end = scroll_points(
            self.adb,
            base_distance_y=BASE_CARD_SCROLL_DISTANCE_Y,
            direction="up",
        )
        swipe(self.adb, start, end, wait=0.8)
        return ActionResult.ok(wait=0.6)

    def _tap_target_card_by_scan(self, detected) -> Optional[ActionResult]:
        """通过 YOLO+Hash 扫描定位目标卡牌并点击。"""
        if not detected:
            return None

        candidates = [
            item
            for item in detected
            if item.set_code == FIXED_CARD_SET_CODE
            and item.card_number == FIXED_CARD_NUMBER
        ]
        if not candidates:
            return None

        best = max(candidates, key=lambda item: (item.similarity, item.confidence))
        return tap(self.adb, int(best.center[0]), int(best.center[1]), wait=1.0)

    @staticmethod
    def _build_detect_signature(detected) -> str:
        """构建扫描结果签名，用于判断列表是否变化。"""
        if not detected:
            return "__EMPTY__"
        items: list[str] = []
        for item in detected:
            if not item.set_code:
                continue
            items.append(f"{item.set_code}:{item.card_number}")
        if not items:
            return "__EMPTY__"
        return "|".join(sorted(items))

    def _handle_filter_modal(self, page_info: dict) -> ActionResult:
        """筛选弹窗：清空 -> 输入关键字 -> 确认，若仍停留则重复该循环。"""
        ocr_results = page_info.get("ocr_results", [])

        # 若连续停留在筛选弹窗，重置流程，强制再次「清除 -> 输入 -> OK」。
        if self._is_action_done("filter_keyword_input"):
            self._filter_modal_stay_rounds += 1
        else:
            self._filter_modal_stay_rounds = 0

        if self._filter_modal_stay_rounds >= MAX_FILTER_MODAL_STAY_ROUNDS:
            self._action_cache.pop("filter_clear_clicked", None)
            self._action_cache.pop("filter_keyword_input", None)
            self._filter_modal_stay_rounds = 0

        if not self._is_action_done("filter_clear_clicked"):
            clear_button = tap_text_exact(
                self.adb,
                ocr_results,
                get_text_patterns("gift_filter_clear"),
                wait=0.5,
            )
            if clear_button:
                self._mark_action_done("filter_clear_clicked")
                return clear_button

        if not self._is_action_done("filter_keyword_input"):
            focus_point = self._get_filter_search_focus_point()
            if focus_point is not None:
                clear_text(
                    self.adb,
                    focus_point[0],
                    focus_point[1],
                    max_chars=40,
                    wait=0.2,
                )
                input_text(
                    self.adb,
                    get_text_patterns("gift_search_keyword_marowak")[0],
                    wait=0.3,
                )
                self._mark_action_done("filter_keyword_input")
                return ActionResult.wait(0.6)

        ok_result = tap_ok(self.adb, ocr_results, wait=1.0)
        if ok_result:
            self._filter_applied = True
            # 允许在“点击 OK 后仍停留弹窗”的情况下，下次再次执行完整清除+输入流程。
            self._action_cache.pop("filter_clear_clicked", None)
            self._action_cache.pop("filter_keyword_input", None)
            self._filter_modal_stay_rounds = 0
            return ok_result
        return ActionResult.wait(0.6)

    def _get_filter_search_focus_point(self) -> Optional[tuple[int, int]]:
        """根据 icon_search 计算筛选输入框点击点。"""
        box = self.page_detector.find_template("icon_search", threshold=0.8)
        if not box:
            match = self.page_detector.find_template_with_scale(
                "icon_search", scale=1.0, threshold=0.8
            )
            if match:
                box = match.box
        if not box:
            return None
        return self.adb.center_x(), (box[1] + box[3]) // 2

    def _handle_target_page(self, page_info: dict) -> ActionResult:
        """目标确认页：解析持有数量并点击分送。"""
        ocr_results = page_info.get("ocr_results", [])
        if self._before_count is None or self._after_count is None:
            self._extract_hold_counts(ocr_results)

        if not is_text_visible(
            ocr_results,
            get_text_patterns("gift_hold_count"),
            exact=False,
        ):
            return ActionResult.wait(0.6)

        send_result = tap_text_exact(
            self.adb,
            ocr_results,
            get_text_patterns("gift_send_button"),
            wait=0.8,
        )
        if send_result:
            if self._record:
                GiftRecordService.update_status(self._record, status="confirming")
            return send_result
        return ActionResult.wait(0.6)

    def _extract_hold_counts(self, ocr_results: list[dict]):
        """从 OCR 文本中提取持有数量变化。"""
        for item in ocr_results:
            text = str(item.get("text", ""))
            before_count, after_count = GiftRecordService.parse_count_transition(text)
            if before_count is not None and after_count is not None:
                self._before_count = before_count
                self._after_count = after_count
                return

    def _handle_confirm_popup(self, page_info: dict) -> ActionResult:
        """确认弹窗点击 OK。"""
        result = tap_ok(self.adb, page_info.get("ocr_results", []), wait=0.8)
        return result or ActionResult.wait(0.6)

    def _handle_confirm_last_popup(self, page_info: dict) -> ActionResult:
        """仅剩一张弹窗点击 OK。"""
        result = tap_ok(self.adb, page_info.get("ocr_results", []), wait=0.8)
        return result or ActionResult.wait(0.6)

    def _handle_swipe_page(self, page_info: dict) -> ActionResult:
        """送卡成功页：执行上滑并落库。"""
        if self._is_action_done("swiped"):
            return ActionResult.ok(wait=0.5)

        swipe_result = swipe_card_register(self.adb, wait=1.0)
        if not swipe_result.success:
            return swipe_result

        self._mark_action_done("swiped")
        self._finalize_success()
        self._completed = True
        return ActionResult.ok(wait=0.8)

    def _finalize_success(self):
        """任务成功后的记录与库存同步。"""
        if not self._record:
            return
        self._record = GiftRecordService.mark_success_and_sync_count(
            record=self._record,
            card_id=self._fixed_card_id,
            before_count=self._before_count,
            after_count=self._after_count,
        )
        self._gift_sent_success = True

    def _maybe_complete_for_pair_ordering(self):
        """根据双向配对库存与当日执行情况决定是否等待对方先送。"""
        if not self._record or not isinstance(self._target_account_id, int):
            return
        if not self._target_friend_id or self.account.id is None:
            return

        my_id = int(self.account.id)
        peer_id = int(self._target_account_id)
        my_friend_id = self.account.friend_id
        if not my_friend_id:
            return

        peer_sent_to_me = GiftRecordService.is_daily_success(
            account_id=peer_id,
            target_friend_id=my_friend_id,
        )
        if peer_sent_to_me:
            return

        my_count = self._get_fixed_card_count(my_id)
        peer_count = self._get_fixed_card_count(peer_id)

        if my_count <= 0 and peer_count <= 0:
            self._complete_without_send(
                complete_reason="双方当前均无目标卡，结束本次送卡任务",
                record_status="completed_no_card",
                error_code="PAIR_BOTH_NO_CARD",
            )
            return

        if my_count <= 0 < peer_count:
            GiftRecordService.ensure_send_card_daily_pending(account_id=peer_id)
            self._complete_without_send(
                complete_reason="当前账号无卡且对方有卡，等待对方先送",
                record_status="completed_wait_peer_first",
                error_code="WAIT_PEER_FIRST",
            )
            return

        if my_count > 0 and peer_count <= 0:
            return

        if my_count > 0 and peer_count > 0 and my_id > peer_id:
            if GiftRecordService.has_daily_attempt(
                account_id=peer_id,
                target_friend_id=my_friend_id,
            ):
                logger.info("对端今日已尝试送卡，跳过稳定顺序等待，当前账号优先送卡")
                return
            GiftRecordService.ensure_send_card_daily_pending(account_id=peer_id)
            self._skip_without_send(
                skip_reason="双方均有卡，按稳定顺序等待小ID账号先送",
                record_status="completed_wait_peer_first",
                error_code="WAIT_STABLE_ORDER",
            )

    def _get_fixed_card_count(self, account_id: int) -> int:
        """读取账号当前固定目标卡库存数量。"""
        if self._fixed_card_id is None:
            return 0
        row = AccountCardRepository().get(account_id, self._fixed_card_id)
        if row is None:
            return 0
        return max(int(row.count), 0)
