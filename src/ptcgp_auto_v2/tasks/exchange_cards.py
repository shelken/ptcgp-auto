# -*- coding: utf-8 -*-
"""交换卡牌任务。

按 ExchangeCardRequest 状态机执行 sending / sended 两阶段流程。
任务本身始终收敛为完成态，业务失败写入 request。
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Optional

from ptcgp_auto_v2.core.task_base import ActionResult, ResetType, Task, TaskRegistry
from ptcgp_auto_v2.db.models import ExchangeCardRequest
from ptcgp_auto_v2.db.repositories import (
    AccountCardRepository,
    CardRepository,
    ExchangeCardRequestRepository,
    FriendshipRepository,
)
from ptcgp_auto_v2.hooks import ExchangeDelayPostHook
from ptcgp_auto_v2.hooks.friend_hooks import FriendPreHook
from ptcgp_auto_v2.infra.card_hash_manager import get_card_hash_manager
from ptcgp_auto_v2.infra.icon_group_detector import IconGroupDetector
from ptcgp_auto_v2.infra.model_manager import get_model_manager
from ptcgp_auto_v2.infra.yolo_card_recognizer import YoloCardRecognizer
from ptcgp_auto_v2.locales import get_text_patterns
from ptcgp_auto_v2.services import ExchangeCardService
from ptcgp_auto_v2.tasks.utils.constants import (
    BASE_CARD_SCROLL_DISTANCE_Y,
    MAX_CARD_STABLE_ROUNDS,
)
from ptcgp_auto_v2.tasks.utils.friend_card_flow import build_detect_signature
from ptcgp_auto_v2.tasks.utils.friend_selection_flow import (
    FriendSelectionFlow,
    FriendSelectionHelper,
)
from ptcgp_auto_v2.tasks.utils.rarity_filter import (
    FilterPanelState,
    handle_filter_panel,
)
from ptcgp_auto_v2.utils.account_cooldown import is_account_past_days
from ptcgp_auto_v2.utils.card_name_resolver import resolve_card_name
from ptcgp_auto_v2.utils.gesture import (
    is_text_visible,
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

RECHECK_DELAY_SECONDS = 300


@dataclass
class ExchangeRuntimeState:
    """任务运行态。"""

    current_request: Optional[ExchangeCardRequest] = None
    completed: bool = False
    complete_reason: Optional[str] = None
    delay_seconds: Optional[float] = None
    delay_reason: Optional[str] = None


@dataclass
class ExchangeCardState:
    """目标卡牌状态。"""

    name: Optional[str] = None
    set_code: Optional[str] = None
    number: Optional[int] = None


@dataclass
class ExchangeTaskContext:
    """交换任务上下文。"""

    runtime: ExchangeRuntimeState = field(default_factory=ExchangeRuntimeState)
    card: ExchangeCardState = field(default_factory=ExchangeCardState)
    friend_flow: FriendSelectionFlow = field(default_factory=FriendSelectionFlow)

    def reset(self):
        """重置任务上下文。"""
        self.runtime = ExchangeRuntimeState()
        self.card = ExchangeCardState()
        self.friend_flow = FriendSelectionFlow()


def _build_exchange_pages() -> list[dict]:
    """构建交换任务页面识别规则。

    页面流转顺序（priority 越小越先匹配）：

    sending 流程：
      主页(10/20) → 社群(30) → 交换主页(40) → 选择好友(50) → 好友详情(55) →
      选卡(60) → 筛选(65) → 确认页(70) → 发送弹窗(75) → 仅剩弹窗(76) → 提议完成(77)

    sended 流程：
      主页(10/20) → 社群(30) → 交换主页sended(41) → 点击確認 →
        对方已送：receive_confirm(81) → receive_start(82)
        对方未送：waiting_page(80) → cancel_confirm(83) → canceled_done(84)
    """
    return [
        # ===== 通用入口页面 =====
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
            "priority": 30,
        },
        # ===== sending 流程 =====
        {
            "name": "exchange_page_main",
            "identifiers": get_text_patterns("exchange_page"),
            "match_all": True,
            "priority": 40,
        },
        {
            "name": "exchange_page_sended",
            "identifiers": get_text_patterns("exchange_page_sended"),
            "priority": 41,
        },
        {
            "name": "exchange_choose_friend",
            "identifiers": get_text_patterns("exchange_choose_friend_title"),
            "priority": 50,
        },
        {
            "name": "friend_profile",
            "identifiers": get_text_patterns("friend_profile"),
            "priority": 55,
        },
        {
            "name": "exchange_select_card",
            "identifiers": get_text_patterns("exchange_select_card_title"),
            "match_all": True,
            "priority": 60,
        },
        {
            "name": "exchange_filter_modal",
            "identifiers": get_text_patterns("card_filter_title"),
            "priority": 65,
        },
        {
            "name": "exchange_target_confirm_page",
            "identifiers": get_text_patterns("exchange_target_confirm_page"),
            "match_all": True,
            "exclude_identifiers": get_text_patterns("exchange_waiting_page"),
            "priority": 70,
        },
        {
            "name": "exchange_confirm_send_popup",
            "identifiers": get_text_patterns("exchange_confirm_send_popup"),
            "priority": 75,
        },
        {
            "name": "exchange_confirm_last_popup",
            "identifiers": get_text_patterns("exchange_confirm_last_card_popup"),
            "priority": 76,
        },
        {
            "name": "exchange_proposed_done_popup",
            "identifiers": get_text_patterns("exchange_proposed_done_popup"),
            "priority": 77,
        },
        # ===== sended 流程 =====
        {
            "name": "exchange_waiting_page",
            "identifiers": get_text_patterns("exchange_waiting_page"),
            "match_all": True,
            "priority": 80,
        },
        {
            "name": "exchange_receive_confirm_page",
            "identifiers": get_text_patterns("exchange_receive_confirm_page"),
            "match_all": True,
            "priority": 81,
        },
        {
            "name": "exchange_receive_start_popup",
            "identifiers": get_text_patterns("exchange_receive_start_popup"),
            "priority": 82,
        },
        {
            "name": "exchange_cancel_confirm_popup",
            "identifiers": get_text_patterns("exchange_cancel_confirm_popup"),
            "priority": 83,
        },
        {
            "name": "exchange_canceled_done_popup",
            "identifiers": get_text_patterns("exchange_canceled_done_popup"),
            "priority": 84,
        },
    ]


@TaskRegistry.register("exchange_cards")
class ExchangeCardsTask(Task):
    """交换卡牌任务。"""

    task_type = "exchange_cards"
    reset_type = ResetType.ONCE
    pages = _build_exchange_pages()
    max_unknown_pages = 20
    max_iterations = 220

    def __init__(self, adb, recognizer, page_detector):
        super().__init__(adb, recognizer, page_detector)
        self._ctx = ExchangeTaskContext()
        self._request_repo = ExchangeCardRequestRepository()
        self._account_card_repo = AccountCardRepository()
        self._card_repo = CardRepository()
        self._icon_detector = IconGroupDetector()
        self._card_recognizer = YoloCardRecognizer(
            adb=adb,
            model_manager=get_model_manager(),
            hash_manager=get_card_hash_manager(),
        )
        self._card_stable_rounds = 0
        self._last_card_signature: Optional[str] = None
        self._action_cache: dict[str, bool] = {}
        self._filter_state = FilterPanelState()
        self._friend_helper: Optional[FriendSelectionHelper] = None

    def on_start(self):
        """加载请求并执行前置校验。"""
        self._ctx.reset()
        self._card_stable_rounds = 0
        self._last_card_signature = None
        self._action_cache = {}
        self._filter_state = FilterPanelState()

        if self.account.id is None:
            self._ctx.runtime.completed = True
            self._ctx.runtime.complete_reason = "账号ID为空"
            return

        request = self._request_repo.get_active_by_account(self.account.id)
        if request is None:
            self._ctx.runtime.completed = True
            self._ctx.runtime.complete_reason = "无活跃交换请求"
            return
        self._ctx.runtime.current_request = request

        if not is_account_past_days(self.account.created_at, 14):
            self._fail_request("账号未过14天冷静期")
            return

        if request.status == "sending":
            account_card = self._account_card_repo.get(
                self.account.id, request.target_card_id
            )
            if account_card is None or account_card.count < 1:
                self._fail_request("目标卡牌库存不足")
                return

        request_nickname = getattr(request, "to_nickname", None)
        if request_nickname:
            self._ctx.friend_flow.nickname = request_nickname
        else:
            friendship = FriendshipRepository().get_friendship(
                account_id=self.account.id,
                friend_id=request.to_friend_id,
            )
            if friendship and friendship.friend_nickname:
                self._ctx.friend_flow.nickname = friendship.friend_nickname
                logger.info(
                    "从好友关系读取昵称: %s -> %s",
                    request.to_friend_id,
                    friendship.friend_nickname,
                )

        card = self._card_repo.get_by_id(request.target_card_id)
        if card is not None:
            self._ctx.card.name = resolve_card_name(
                self._card_repo,
                card.set_code,
                card.number,
            )
            self._ctx.card.set_code = card.set_code
            self._ctx.card.number = card.number

        self._init_friend_helper()
        self._preflight_validate()

    def _init_friend_helper(self):
        """初始化好友选择辅助类。"""
        request = self._ctx.runtime.current_request
        if request is None:
            return

        self._friend_helper = FriendSelectionHelper(
            adb=self.adb,
            page_detector=self.page_detector,
            flow=self._ctx.friend_flow,
            target_friend_id=request.to_friend_id or "",
            profile_page_name="friend_profile",
            send_text_patterns=get_text_patterns("exchange_send_button"),
            on_nickname_found=self._on_nickname_found,
            on_scroll_exhausted=self._on_scroll_exhausted,
        )

    def _on_nickname_found(self, account_id: int, friend_id: str, nickname: str):
        """发现 nickname 回调：持久化到好友关系。"""
        FriendshipRepository().update_nickname(
            account_id=account_id,
            friend_id=friend_id,
            nickname=nickname,
        )

    def _on_scroll_exhausted(self, reason: str) -> ActionResult:
        """滑动耗尽回调。"""
        return self._fail_and_complete(reason)

    def _preflight_validate(self):
        """任务启动时统一执行前置校验。"""
        if self._ctx.runtime.current_request is None:
            return

        request = self._ctx.runtime.current_request
        rarity_code = (request.target_card_rarity or "").upper()

        if request.status not in {"sending", "sended"}:
            self._fail_request(f"请求状态非法: {request.status}")
            return

        if rarity_code in ExchangeCardService.NON_EXCHANGEABLE_RARITIES:
            self._fail_request("目标稀有度不可交换")
            return

        if rarity_code not in ExchangeCardService.EXCHANGE_POINT_COSTS:
            self._fail_request(f"不支持的目标稀有度: {rarity_code}")
            return

        if not self._ctx.card.set_code or self._ctx.card.number is None:
            self._fail_request("目标卡牌不存在，无法执行交换")
            return

        if request.status == "sending" and not self._ctx.card.name:
            self._fail_request("目标卡牌名称缺失，无法在确认页核验")
            return

    def get_pre_hooks(self) -> list:
        """前置 Hook：确保好友关系。"""
        if self._ctx.runtime.completed or self._ctx.runtime.current_request is None:
            return []
        target_friend_id = (
            self._ctx.runtime.current_request.to_friend_id or ""
        ).strip()
        if not target_friend_id:
            return []
        return [
            FriendPreHook(
                target_friend_id=target_friend_id,
                target_account_id=self._ctx.runtime.current_request.to_account_id,
                target_nickname=self._ctx.friend_flow.nickname,
            )
        ]

    def get_post_hooks(self) -> list:
        """后置 Hook：支持延时复查。"""
        return [ExchangeDelayPostHook()]

    def is_completed(self) -> bool:
        """任务是否收敛。"""
        return self._ctx.runtime.completed

    def handle_page(self, page_name: str, page_info: dict) -> ActionResult:
        """按页面分发处理。"""
        if self._ctx.runtime.current_request is None:
            self._ctx.runtime.completed = True
            return ActionResult.ok(wait=0.2)

        if page_name in {"home_with_community_icon", "game_home_main"}:
            return self._handle_home(page_info)
        if page_name == "community_page":
            return self._handle_community(page_info)
        if page_name in {"exchange_page_main", "exchange_page_sended"}:
            return self._handle_exchange_page_main(page_info)

        if self._ctx.runtime.current_request.status == "sending":
            return self._handle_sending_pages(page_name, page_info)

        if self._ctx.runtime.current_request.status == "sended":
            return self._handle_sended_pages(page_name, page_info)

        self._ctx.runtime.completed = True
        self._ctx.runtime.complete_reason = (
            f"请求状态不可处理: {self._ctx.runtime.current_request.status}"
        )
        return ActionResult.ok(wait=0.2)

    def _handle_sending_pages(self, page_name: str, page_info: dict) -> ActionResult:
        """sending 阶段页面处理。"""
        handlers = {
            "exchange_choose_friend": self._handle_choose_friend,
            "exchange_select_card": self._handle_select_card,
            "exchange_filter_modal": self._handle_filter_modal,
            "exchange_target_confirm_page": self._handle_target_confirm_page,
            "exchange_confirm_send_popup": self._tap_ok_popup,
            "exchange_confirm_last_popup": self._tap_ok_popup,
            "exchange_proposed_done_popup": self._handle_proposed_done_popup,
        }
        handler = handlers.get(page_name)
        if handler:
            return handler(page_info)
        return ActionResult.wait(0.6)

    def _handle_sended_pages(self, page_name: str, page_info: dict) -> ActionResult:
        """sended 阶段页面处理。"""
        handlers = {
            "exchange_waiting_page": self._handle_waiting_page,
            "exchange_receive_confirm_page": self._handle_receive_confirm_page,
            "exchange_receive_start_popup": self._handle_receive_start_popup,
            "exchange_cancel_confirm_popup": self._tap_ok_popup,
            "exchange_canceled_done_popup": self._handle_canceled_done_popup,
        }
        handler = handlers.get(page_name)
        if handler:
            return handler(page_info)
        return ActionResult.wait(0.6)

    def _handle_home(self, page_info: dict) -> ActionResult:
        """主页进入社群。"""
        return tap_community_icon(self.adb, self.page_detector, wait=1.0)

    def _handle_community(self, page_info: dict) -> ActionResult:
        """社群页面进入交换入口。"""
        ocr_results = page_info.get("ocr_results", [])
        result = tap_text_exact(
            self.adb,
            ocr_results,
            get_text_patterns("community_exchange_btn"),
            wait=1.0,
        )
        return result or ActionResult.wait(0.8)

    def _handle_exchange_page_main(self, page_info: dict) -> ActionResult:
        """交换主页：sending 点击交换，sended 点击确认。"""
        if self._ctx.runtime.current_request is None:
            return ActionResult.wait(0.6)
        ocr_results = page_info.get("ocr_results", [])
        request = self._ctx.runtime.current_request

        if request.status == "sending":
            result = tap_text_exact(
                self.adb,
                ocr_results,
                get_text_patterns("exchange_send_button"),
                wait=0.8,
            )
            return result or ActionResult.wait(0.6)

        if request.status == "sended":
            has_confirm = is_text_visible(
                ocr_results, get_text_patterns("exchange_confirm_button"), exact=False
            )
            if has_confirm:
                result = tap_text_exact(
                    self.adb,
                    ocr_results,
                    get_text_patterns("exchange_confirm_button"),
                    wait=0.8,
                )
                return result or ActionResult.wait(0.6)
            else:
                logger.info("sended 状态但未看到確認按钮，交换已失效，标记取消")
                self._request_repo.mark_canceled(request, reason="交换已失效")
                self._ctx.runtime.completed = True
                self._ctx.runtime.complete_reason = "交换已失效"
                return ActionResult.ok(wait=0.3)

        logger.warning("请求状态不可处理: %s", request.status)
        return ActionResult.wait(0.6)

    def _handle_choose_friend(self, page_info: dict) -> ActionResult:
        """请选择朋友页面：先核验 friend_id，再点击对应交换。"""
        if self._friend_helper is None or self._ctx.runtime.current_request is None:
            return ActionResult.wait(0.6)

        ocr_results = page_info.get("ocr_results", [])

        if is_text_visible(
            ocr_results,
            get_text_patterns("gift_choose_friend_empty"),
            exact=False,
        ):
            return self._fail_and_complete("好友列表为空，无法执行交换")

        if self._friend_helper.update_signature_and_check_stable(ocr_results):
            return self._friend_helper.scroll_or_fail()

        if self._ctx.friend_flow.friend_verified:
            send_box = self._friend_helper.find_send_box_by_anchor(ocr_results)
            if send_box:
                return tap_box(self.adb, send_box, wait=1.0)
            return self._friend_helper.scroll_or_fail()

        if self._ctx.friend_flow.nickname:
            plus_box = self._friend_helper.find_plus_for_nickname(
                ocr_results, self._ctx.friend_flow.nickname
            )
            if plus_box:
                return self._friend_helper.tap_plus_and_wait_profile(plus_box)
            return self._friend_helper.scroll_or_fail()

        probe_box = self._friend_helper.get_next_probe_box()
        if probe_box:
            return self._friend_helper.tap_plus_and_wait_profile(probe_box)
        return self._friend_helper.scroll_or_fail()

    def _handle_select_card(self, page_info: dict) -> ActionResult:
        """选卡页面：筛选稀有度，扫描目标卡并点击。"""
        if self._ctx.runtime.current_request is None:
            return ActionResult.wait(0.6)
        ocr_results = page_info.get("ocr_results", [])

        if self._is_action_done("target_card_tapped"):
            if is_text_visible(
                ocr_results,
                get_text_patterns("exchange_insufficient_points"),
                exact=False,
            ):
                return self._fail_and_complete("点击目标卡后检测到交换点数不足")
            ok_result = tap_ok(self.adb, ocr_results, wait=1.0)
            logger.info("点击卡牌后点击 OK")
            return ok_result or ActionResult.wait(0.5)

        if not self._is_action_done("open_filter_clicked"):
            result = tap_template(self.adb, self.page_detector, "icon_search", wait=1.0)
            if result:
                self._mark_action_done("open_filter_clicked")
                return result

        if not self._is_action_done("filter_applied"):
            return ActionResult.wait(0.6)

        detected = self._card_recognizer.scan(
            set_code=self._ctx.card.set_code,
            debug=False,
        )
        tap_result = self._tap_target_card_by_scan(detected)
        if tap_result:
            self._card_stable_rounds = 0
            self._last_card_signature = None
            self._mark_action_done("target_card_tapped")
            logger.info(
                "点击目标卡牌: set_code=%s, number=%s",
                self._ctx.card.set_code,
                self._ctx.card.number,
            )
            return tap_result

        card_signature = build_detect_signature(detected)
        if card_signature == self._last_card_signature:
            self._card_stable_rounds += 1
        else:
            self._card_stable_rounds = 0
            self._last_card_signature = card_signature

        if self._card_stable_rounds >= MAX_CARD_STABLE_ROUNDS:
            return self._fail_and_complete("连续三次扫描未找到目标卡牌")

        start, end = scroll_points(
            self.adb,
            base_distance_y=BASE_CARD_SCROLL_DISTANCE_Y,
            direction="up",
        )
        swipe(self.adb, start, end, wait=0.8)
        return ActionResult.ok(wait=0.6)

    def _handle_filter_modal(self, page_info: dict) -> ActionResult:
        """筛选弹窗：按目标稀有度执行完整筛选流程。"""
        if self._ctx.runtime.current_request is None:
            return ActionResult.wait(0.6)

        rarity_code = (
            self._ctx.runtime.current_request.target_card_rarity or ""
        ).upper()
        rarity_codes = [rarity_code] if rarity_code else []

        result = handle_filter_panel(
            adb=self.adb,
            page_detector=self.page_detector,
            icon_detector=self._icon_detector,
            page_info=page_info,
            rarity_codes=rarity_codes,
            state=self._filter_state,
            action_cache=self._action_cache,
        )

        if self._is_action_done("filter_selected") and self._is_action_done(
            "filter_ok_scrolled"
        ):
            self._mark_action_done("filter_applied")

        return result

    def _handle_target_confirm_page(self, page_info: dict) -> ActionResult:
        """送卡确认页面：校验目标昵称后点击 OK。"""
        if self._ctx.runtime.current_request is None:
            return ActionResult.wait(0.6)
        ocr_results = page_info.get("ocr_results", [])

        if self._ctx.friend_flow.nickname and not is_text_visible(
            ocr_results,
            [self._ctx.friend_flow.nickname],
            exact=False,
        ):
            return self._fail_and_complete("确认页目标昵称不匹配")

        if self._ctx.card.set_code and self._ctx.card.number:
            detected = self._card_recognizer.scan(
                set_code=self._ctx.card.set_code,
                debug=False,
            )
            candidates = [
                item
                for item in detected
                if item.set_code == self._ctx.card.set_code
                and item.card_number == self._ctx.card.number
            ]
            if not candidates:
                logger.warning(
                    "确认页扫描未匹配到目标卡牌: set_code=%s, number=%s",
                    self._ctx.card.set_code,
                    self._ctx.card.number,
                )
                return self._fail_and_complete("确认页卡牌不匹配")
            logger.info(
                "确认页扫描匹配到目标卡牌: set_code=%s, number=%s, similarity=%.2f",
                self._ctx.card.set_code,
                self._ctx.card.number,
                candidates[0].similarity,
            )

        result = tap_ok(self.adb, ocr_results, wait=0.8)
        return result or ActionResult.wait(0.6)

    def _tap_ok_popup(self, page_info: dict) -> ActionResult:
        """通用弹窗：点击 OK。"""
        result = tap_ok(self.adb, page_info.get("ocr_results", []), wait=0.8)
        return result or ActionResult.wait(0.6)

    def _handle_proposed_done_popup(self, page_info: dict) -> ActionResult:
        """提议完成弹窗：确认后写入 sended 并延时复查。"""
        if self._ctx.runtime.current_request is None:
            return ActionResult.wait(0.6)
        result = tap_ok(self.adb, page_info.get("ocr_results", []), wait=0.8)
        if not result:
            return ActionResult.wait(0.6)

        self._request_repo.mark_sended(
            self._ctx.runtime.current_request,
            next_check_at=datetime.now() + timedelta(seconds=RECHECK_DELAY_SECONDS),
        )
        self._set_delay("交换请求已送出，等待复查")
        self._ctx.runtime.completed = True
        self._ctx.runtime.complete_reason = "交换请求已送出，等待复查"
        return result

    def _handle_waiting_page(self, page_info: dict) -> ActionResult:
        """等待对方回应页面：超时/取消走取消链路，否则延后复查。"""
        if self._ctx.runtime.current_request is None:
            return ActionResult.wait(0.6)
        now = datetime.now()

        cancel_reason = self._ctx.runtime.current_request.cancel_reason
        if (
            not cancel_reason
            and self._ctx.runtime.current_request.expire_at
            and now >= self._ctx.runtime.current_request.expire_at
        ):
            cancel_reason = "等待对方回应超时，自动取消"

        if cancel_reason:
            if not self._is_action_done("waiting_cancel_clicked"):
                cancel_result = tap_text_exact(
                    self.adb,
                    page_info.get("ocr_results", []),
                    get_text_patterns("exchange_cancel_button"),
                    wait=0.8,
                )
                if cancel_result:
                    self._mark_action_done("waiting_cancel_clicked")
                    return cancel_result
            return ActionResult.wait(0.6)

        self._ctx.runtime.current_request.next_check_at = now + timedelta(
            seconds=RECHECK_DELAY_SECONDS
        )
        self._ctx.runtime.current_request.updated_at = now
        self._request_repo.update(self._ctx.runtime.current_request)
        self._set_delay("等待对方回应，延时复查")
        self._ctx.runtime.completed = True
        self._ctx.runtime.complete_reason = "等待对方回应，延时复查"
        return ActionResult.ok(wait=0.4)

    def _handle_receive_confirm_page(self, page_info: dict) -> ActionResult:
        """对方已回应页面：确认交换或拒绝。"""
        if self._ctx.runtime.current_request is None:
            return ActionResult.wait(0.6)
        ocr_results = page_info.get("ocr_results", [])

        if self._ctx.runtime.current_request.cancel_reason:
            reject_result = tap_text_exact(
                self.adb,
                ocr_results,
                get_text_patterns("exchange_reject_button"),
                wait=0.8,
            )
            return reject_result or ActionResult.wait(0.6)

        exchange_result = tap_text_exact(
            self.adb,
            ocr_results,
            get_text_patterns("exchange_send_button"),
            wait=0.8,
        )
        return exchange_result or ActionResult.wait(0.6)

    def _handle_receive_start_popup(self, page_info: dict) -> ActionResult:
        """开始交换确认弹窗：OK 后标记 completed。"""
        if self._ctx.runtime.current_request is None:
            return ActionResult.wait(0.6)
        result = tap_ok(self.adb, page_info.get("ocr_results", []), wait=0.8)
        if not result:
            return ActionResult.wait(0.6)
        self._request_repo.mark_completed(self._ctx.runtime.current_request)
        self._ctx.runtime.completed = True
        self._ctx.runtime.complete_reason = "交换完成"
        return result

    def _handle_canceled_done_popup(self, page_info: dict) -> ActionResult:
        """取消完成弹窗：点击 OK 并落库 canceled。"""
        if self._ctx.runtime.current_request is None:
            return ActionResult.wait(0.6)
        result = tap_ok(self.adb, page_info.get("ocr_results", []), wait=0.8)
        if not result:
            return ActionResult.wait(0.6)

        reason = self._ctx.runtime.current_request.cancel_reason or "交换已取消"
        self._request_repo.mark_canceled(
            self._ctx.runtime.current_request, reason=reason
        )
        self._ctx.runtime.completed = True
        self._ctx.runtime.complete_reason = "交换已取消"
        return result

    def _set_delay(self, reason: str):
        """设置后置 Hook 使用的延时信息。"""
        self._ctx.runtime.delay_seconds = float(RECHECK_DELAY_SECONDS)
        self._ctx.runtime.delay_reason = reason

    def _fail_request(self, reason: str):
        """将当前请求标记失败并结束任务。"""
        if self._ctx.runtime.current_request is not None:
            self._request_repo.mark_failed(self._ctx.runtime.current_request, reason)
        self._ctx.runtime.completed = True
        self._ctx.runtime.complete_reason = reason

    def _fail_and_complete(self, reason: str) -> ActionResult:
        """失败收敛快捷入口。"""
        self._fail_request(reason)
        return ActionResult.ok(wait=0.3)

    def _mark_action_done(self, action_name: str):
        """标记页面动作已完成。"""
        self._action_cache[action_name] = True

    def _is_action_done(self, action_name: str) -> bool:
        """查询页面动作是否完成。"""
        return self._action_cache.get(action_name, False)

    def _tap_target_card_by_scan(self, detected) -> Optional[ActionResult]:
        """通过 YOLO+Hash 扫描定位目标卡牌。"""
        if not detected:
            return None
        if self._ctx.card.set_code is None or self._ctx.card.number is None:
            return None

        candidates = [
            item
            for item in detected
            if item.set_code == self._ctx.card.set_code
            and item.card_number == self._ctx.card.number
        ]
        if not candidates:
            return None

        best = max(candidates, key=lambda item: (item.similarity, item.confidence))
        return tap(self.adb, int(best.center[0]), int(best.center[1]), wait=0.8)
