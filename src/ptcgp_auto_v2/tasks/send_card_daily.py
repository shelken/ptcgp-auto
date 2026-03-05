# -*- coding: utf-8 -*-
"""
每日送卡任务。

初版策略：
1. 自动配对系统内账号（稳定关系，缺失时增量补齐）
2. 固定送出 A1-153（嘎啦嘎啦）
3. 成功后记录流水并同步 account_cards 剩余数量
"""

import logging
from typing import Optional

from ptcgp_auto_v2.core.task_base import ActionResult, ResetType, Task, TaskRegistry
from ptcgp_auto_v2.db.repositories import (
    AccountCardRepository,
    AccountRepository,
    CardRepository,
    FriendshipRepository,
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
from ptcgp_auto_v2.tasks.utils.constants import (
    BASE_CARD_SCROLL_DISTANCE_Y,
    MAX_CARD_STABLE_ROUNDS,
)
from ptcgp_auto_v2.tasks.utils.friend_card_flow import build_detect_signature
from ptcgp_auto_v2.tasks.utils.friend_selection_flow import (
    FriendSelectionFlow,
    FriendSelectionHelper,
)
from ptcgp_auto_v2.tasks.utils.pack_opening_flow import swipe_card_register
from ptcgp_auto_v2.utils.account_cooldown import is_account_pending_same_day_cooldown
from ptcgp_auto_v2.utils.gesture import (
    clear_text,
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

FIXED_CARD_SET_CODE = "A1"
FIXED_CARD_NUMBER = 153
MAX_FILTER_MODAL_STAY_ROUNDS = 2


def _build_send_card_pages() -> list[dict]:
    """构建送卡任务页面规则。"""
    return [
        # 開放條件 / 距離開放還剩
        {
            "name": "exchange_locked_popup",
            "identifiers": get_text_patterns("exchange_locked_popup"),
            "priority": 10,
        },
        # 確定要送給對方這張卡牌嗎
        {
            "name": "gift_confirm_popup",
            "identifiers": get_text_patterns("gift_confirm_send_popup"),
            "priority": 10,
        },
        # 將分送僅剩的1張卡牌 / 確定要繼續嗎
        {
            "name": "gift_confirm_last_popup",
            "identifiers": get_text_patterns("gift_confirm_last_card_popup"),
            "priority": 10,
        },
        # 要分送的對象
        {
            "name": "gift_target_page",
            "identifiers": get_text_patterns("gift_target_page"),
            "priority": 50,
            "exact_match": True,
        },
        # 請選擇要分送的卡牌
        {
            "name": "gift_select_card",
            "identifiers": get_text_patterns("gift_select_card_title"),
            "priority": 55,
            "exact_match": True,
        },
        # 向上輕滑卡牌
        {
            "name": "gift_swipe_page",
            "identifiers": get_text_patterns("gift_swipe_to_send"),
            "priority": 99,
        },
        # 請選擇朋友
        {
            "name": "gift_choose_friend",
            "identifiers": get_text_patterns("gift_choose_friend_title"),
            "priority": 99,
        },
        # 朋友ID / 戰績
        {
            "name": "friend_profile",
            "match_all": True,
            "identifiers": get_text_patterns("friend_profile"),
            "priority": 99,
        },
        # 我的最愛 / 清除 / OK
        {
            "name": "gift_filter_modal",
            "identifiers": get_text_patterns("gift_filter_modal_title"),
            "match_all": True,
            "priority": 99,
        },
        # 紀錄 / 分送
        {
            "name": "gift_page_main",
            "identifiers": get_text_patterns("gift_page_main"),
            "match_all": True,
            "priority": 99,
        },
        # 社群 / 他人的收藏
        {
            "name": "community_page",
            "identifiers": get_text_patterns("community_page"),
            "match_all": True,
            "priority": 99,
        },
        # 社群图标
        {
            "name": "home_with_community_icon",
            "templates": ["icon_community"],
            "priority": 99,
        },
        # 商店 / 得卡挑戰
        {
            "name": "game_home_main",
            "identifiers": get_text_patterns("game_home_main"),
            "match_all": True,
            "priority": 99,
        },
    ]


@TaskRegistry.register("send_card_daily")
class SendCardDailyTask(Task):
    """每日送卡任务。"""

    task_type = "send_card_daily"
    reset_type = ResetType.INTERVAL
    max_iterations = 80
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
        self._skip_reason: Optional[str] = None

        self._target_friend_id: Optional[str] = None
        self._target_account_id: Optional[int] = None
        self._fixed_card_id: Optional[int] = None
        self._record = None

        self._card_stable_rounds = 0
        self._last_card_signature: Optional[str] = None

        self._before_count: Optional[int] = None
        self._after_count: Optional[int] = None
        self._gift_sent_success = False
        self._filter_applied = False
        self._filter_opened = False
        self._filter_modal_stay_rounds = 0

        self._friend_flow = FriendSelectionFlow()
        self._friend_helper: Optional[FriendSelectionHelper] = None

    def was_skipped(self) -> bool:
        """任务是否被跳过（不更新 last_completed_at）。"""
        return self._skip_reason is not None

    def _mark_skipped(self, skip_reason: str):
        """统一设置跳过态并结束任务。"""
        self._skip_reason = skip_reason
        self._completed = True

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
        self._skip_reason = None
        self._card_stable_rounds = 0
        self._last_card_signature = None
        self._before_count = None
        self._after_count = None
        self._gift_sent_success = False
        self._fixed_card_id = None
        self._filter_applied = False
        self._filter_opened = False
        self._filter_modal_stay_rounds = 0
        self._prev_page_name = None
        self._reset_action_cache()

        self._friend_flow = FriendSelectionFlow()

        if self.account.id is None:
            self._complete_reason = "账号ID为空"
            self._completed = True
            return

        if not GiftPairingService.is_account_past_cooldown(self.account.created_at):
            cooldown_days = getattr(GiftPairingService, "COOLDOWN_DAYS", 14)
            if not isinstance(cooldown_days, int):
                cooldown_days = 14
            if is_account_pending_same_day_cooldown(
                self.account.created_at,
                cooldown_days,
            ):
                self._mark_skipped("账号未过14天冷冻期（同日待到期）")
                return
            self._complete_reason = "账号未过14天冷冻期"
            self._completed = True
            return

        pair = GiftPairingService.ensure_pairs_for_account(self.account.id)
        if pair is None:
            self._mark_skipped("无可用送卡目标")
            return

        self._target_friend_id = pair.target_friend_id
        self._target_account_id = pair.target_account_id
        if pair.target_account_id is not None:
            target_account = AccountRepository().get_by_id(pair.target_account_id)
            if target_account:
                self._friend_flow.nickname = target_account.nickname

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

        self._init_friend_helper()
        self._maybe_complete_for_pair_ordering()

    def _init_friend_helper(self):
        """初始化好友选择辅助类。"""
        self._friend_helper = FriendSelectionHelper(
            adb=self.adb,
            page_detector=self.page_detector,
            flow=self._friend_flow,
            target_friend_id=self._target_friend_id or "",
            profile_page_name="friend_profile",
            send_text_patterns=get_text_patterns("gift_send_button"),
            account_id=self.account.id,
            on_success=self._on_friend_verified,
            on_nickname_found=self._on_nickname_found,
            on_scroll_exhausted=self._on_scroll_exhausted,
        )

    def _on_friend_verified(self):
        """好友验证成功回调。"""
        if self._record:
            GiftRecordService.update_status(self._record, status="target_found")

    def _on_nickname_found(self, account_id: int, friend_id: str, nickname: str):
        """发现 nickname 回调：持久化到好友关系。"""
        FriendshipRepository().update_nickname(
            account_id=account_id,
            friend_id=friend_id,
            nickname=nickname,
        )

    def _on_scroll_exhausted(self, reason: str) -> ActionResult:
        """滑动耗尽回调：删除好友关系后跳过。"""
        if self.account.id and self._target_friend_id:
            FriendshipRepository().delete(self.account.id, self._target_friend_id)
            logger.info(
                "好友关系已删除: account=%s, friend_id=%s",
                self.account.id,
                self._target_friend_id,
            )
        return self._skip_without_send(
            skip_reason=reason,
            record_status="completed_no_target",
            error_code="TARGET_NOT_FOUND",
        )

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
        previous_page_name = self._last_page_name
        if page_name != self._last_page_name:
            self._prev_page_name = previous_page_name
            self._last_page_name = page_name
            self._reset_action_cache()

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
            "exchange_locked_popup": self._handle_exchange_locked_popup,
            "gift_page_main": self._handle_gift_page_main,
            "gift_choose_friend": self._handle_choose_friend,
            "gift_select_card": self._handle_select_card,
            "gift_filter_modal": self._handle_filter_modal,
            "gift_target_page": self._handle_target_page,
            "gift_confirm_popup": self._handle_confirm_popup,
            "gift_confirm_last_popup": self._handle_confirm_popup,
            "gift_swipe_page": self._handle_swipe_page,
        }
        handler = handlers.get(page_name)
        if handler:
            return handler(page_info)
        return ActionResult.wait(0.8)

    def _complete_without_send(
        self,
        complete_reason: str,
        record_status: str,
        error_code: Optional[str] = None,
    ) -> ActionResult:
        """以完成态收敛任务。"""
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
        """以跳过态收敛任务。"""
        self._mark_skipped(skip_reason)
        logger.info("send_card_daily 跳过收敛: %s", skip_reason)
        if self._record and record_status:
            GiftRecordService.update_status(
                self._record,
                status=record_status,
                error_code=error_code,
                error_message=skip_reason,
            )
        return ActionResult.ok(wait=0.3)

    def _handle_exchange_locked_popup(self, page_info: dict) -> ActionResult:
        """交换/分送未解锁弹窗：点击 OK 并跳过本次任务。"""
        result = tap_ok(self.adb, page_info.get("ocr_results", []), wait=0.8)
        if not result:
            return ActionResult.wait(0.6)
        return self._skip_without_send(
            skip_reason="分送功能未解锁（14天冷冻期未到）",
            record_status="completed_no_target",
            error_code="FEATURE_LOCKED",
        )

    def _handle_home(self, page_info: dict) -> ActionResult:
        """主页点击社群入口。"""
        if self._completed:
            return ActionResult.ok(wait=0.5)
        return tap_community_icon(self.adb, self.page_detector, wait=1.0)

    def _handle_community(self, page_info: dict) -> ActionResult:
        """社群页面点击分送入口。"""
        ocr_results = page_info.get("ocr_results", [])
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
        if self._friend_helper is None:
            return ActionResult.wait(0.6)

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

        if self._friend_helper.update_signature_and_check_stable(ocr_results):
            return self._friend_helper.scroll_or_fail()

        if self._friend_flow.friend_verified:
            send_box = self._friend_helper.find_send_box_by_anchor(ocr_results)
            if send_box:
                self._friend_flow.reset_scroll_state()
                return tap_box(self.adb, send_box, wait=1.0)
            return self._friend_helper.scroll_or_fail()

        if self._friend_flow.nickname:
            plus_box = self._friend_helper.find_plus_for_nickname(
                ocr_results, self._friend_flow.nickname
            )
            if plus_box:
                return self._friend_helper.tap_plus_and_wait_profile(plus_box)
            return self._friend_helper.scroll_or_fail()

        if self._friend_helper.check_scroll_bottom():
            return self._skip_without_send(
                skip_reason="已滑到底部，未找到目标好友",
                record_status="completed_no_target",
                error_code="SCROLL_BOTTOM",
            )

        probe_box = self._friend_helper.get_next_probe_box()
        if probe_box:
            return self._friend_helper.tap_plus_and_wait_profile(probe_box)
        return self._friend_helper.scroll_or_fail()

    def _handle_select_card(self, page_info: dict) -> ActionResult:
        """选卡页面：必须先筛选，再通过扫描定位固定卡牌。"""
        if not self._filter_applied and not self._is_action_done("open_filter_clicked"):
            result = tap_template(self.adb, self.page_detector, "icon_search", wait=1.0)
            if result:
                self._filter_opened = True
                self._mark_action_done("open_filter_clicked")
                return result

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

        signature = build_detect_signature(detected)
        if signature == self._last_card_signature:
            self._card_stable_rounds += 1
        else:
            self._card_stable_rounds = 0
            self._last_card_signature = signature

        if self._card_stable_rounds >= MAX_CARD_STABLE_ROUNDS:
            return self._skip_without_send(
                skip_reason="扫描多次未找到目标卡 A1-153，结束本次送卡任务",
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
        return tap(self.adb, int(best.center[0]), int(best.center[1]), wait=2.5)

    def _handle_filter_modal(self, page_info: dict) -> ActionResult:
        """筛选弹窗：清空 -> 输入关键字 -> 确认。"""
        ocr_results = page_info.get("ocr_results", [])

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
