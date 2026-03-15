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
from ptcgp_auto_v2.tasks.utils.pack_opening_flow import swipe_card_register
from ptcgp_auto_v2.tasks.utils.rarity_filter import (
    FilterPanelState,
    handle_filter_panel,
)
from ptcgp_auto_v2.utils.account_cooldown import (
    is_account_past_days,
    is_account_pending_same_day_cooldown,
)
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

EXCHANGE_WINDOW_SECONDS = 300


@dataclass
class ExchangeRuntimeState:
    """任务运行态。"""

    current_request: Optional[ExchangeCardRequest] = None
    completed: bool = False
    complete_reason: Optional[str] = None
    recover_before_send: bool = False


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
        # 開放條件 / 距離開放還剩
        {
            "name": "exchange_locked_popup",
            "identifiers": get_text_patterns("exchange_locked_popup"),
            "priority": 1,
        },
        # 要確定並開始交換
        {
            "name": "exchange_receive_start_popup",
            "identifiers": get_text_patterns("exchange_receive_start_popup"),
            "priority": 2,
        },
        # 向上輕滑卡牌
        {
            "name": "exchange_swipe_page",
            "identifiers": get_text_patterns("exchange_swipe_to_send"),
            "priority": 2,
        },
        # 要取消並結束交換嗎 / 要拒絕並結束交換嗎
        {
            "name": "exchange_cancel_confirm_popup",
            "identifiers": get_text_patterns("exchange_cancel_confirm_popup"),
            "priority": 3,
        },
        # 交換已取消
        {
            "name": "exchange_canceled_done_popup",
            "identifiers": get_text_patterns("exchange_canceled_done_popup"),
            "priority": 4,
        },
        # 確定要送給對方這張卡牌嗎
        {
            "name": "exchange_confirm_send_popup",
            "identifiers": get_text_patterns("exchange_confirm_send_popup"),
            "priority": 5,
        },
        # 將交換僅剩的1張卡牌
        {
            "name": "exchange_confirm_last_popup",
            "identifiers": get_text_patterns("exchange_confirm_last_card_popup"),
            "priority": 6,
        },
        # 已將卡牌提議給對方 / 處於提議階段的卡牌不會在
        {
            "name": "exchange_proposed_done_popup",
            "identifiers": get_text_patterns("exchange_proposed_done_popup"),
            "match_all": True,
            "priority": 7,
        },
        # ===== 通用入口页面 =====
        # 社群图标
        {
            "name": "home_with_community_icon",
            "templates": ["icon_community"],
            "priority": 10,
        },
        # 商店 / 得卡挑戰
        {
            "name": "game_home_main",
            "identifiers": get_text_patterns("game_home_main"),
            "match_all": True,
            "priority": 20,
        },
        # 社群 / 他人的收藏
        {
            "name": "community_page",
            "identifiers": get_text_patterns("community_page"),
            "match_all": True,
            "priority": 30,
        },
        # ===== sending 流程 =====
        # 紀錄
        {
            "name": "exchange_page_main",
            "identifiers": get_text_patterns("exchange_record_tab"),
            "exact_match": True,
            "priority": 40,
        },
        # 請選擇朋友
        {
            "name": "exchange_choose_friend",
            "identifiers": get_text_patterns("exchange_choose_friend_title"),
            "priority": 50,
        },
        # 朋友ID / 戰績
        {
            "name": "profile_page",
            "match_all": True,
            "identifiers": get_text_patterns("profile_page"),
            "exclude_identifiers": get_text_patterns("profile_page_exclude"),
            "priority": 55,
        },
        # 請選擇要送給對方的卡牌
        {
            "name": "exchange_select_card",
            "identifiers": get_text_patterns("exchange_select_card_title"),
            "match_all": True,
            "priority": 60,
        },
        # 稀有度
        {
            "name": "exchange_filter_modal",
            "identifiers": get_text_patterns("card_filter_title"),
            "priority": 65,
        },
        # 編輯卡牌
        {
            "name": "exchange_target_confirm_page",
            "identifiers": get_text_patterns("exchange_target_confirm_page"),
            "priority": 70,
        },
        # ===== sended 流程 =====
        # 正在等待對方回應
        {
            "name": "exchange_waiting_page",
            "identifiers": get_text_patterns("exchange_waiting_page"),
            "match_all": True,
            "priority": 80,
        },
        # 要和這張卡牌交換嗎
        {
            "name": "exchange_receive_confirm_page",
            "identifiers": get_text_patterns("exchange_receive_confirm_page"),
            "match_all": True,
            "priority": 81,
        },
    ]


@TaskRegistry.register("exchange_cards")
class ExchangeCardsTask(Task):
    """交换卡牌任务。"""

    task_type = "exchange_cards"
    reset_type = ResetType.ONCE
    pages = _build_exchange_pages()
    max_same_page_rounds = 20
    max_iterations = 100
    screenshot_lossless = True

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
        self._skipped = False
        self._skip_reason: Optional[str] = None

    def on_start(self):
        """加载请求并执行前置校验。"""
        self._ctx.reset()
        self._card_stable_rounds = 0
        self._last_card_signature = None
        self._action_cache = {}
        self._filter_state = FilterPanelState()
        self._skipped = False
        self._skip_reason = None

        if self.account.id is None:
            self.mark_completed_without_timestamp("账号ID为空")
            self._ctx.runtime.completed = True
            self._ctx.runtime.complete_reason = "账号ID为空"
            return

        request = self._request_repo.get_active_by_account(self.account.id)
        if request is None:
            self.mark_completed_without_timestamp("无活跃交换请求")
            self._ctx.runtime.completed = True
            self._ctx.runtime.complete_reason = "无活跃交换请求"
            return
        self._ctx.runtime.current_request = request

        now = datetime.now()
        if request.expire_at and now >= request.expire_at:
            if request.status == "sending":
                self._request_repo.mark_canceled(
                    request, reason="交换请求已过期（未送出）"
                )
                self.mark_completed_without_timestamp("交换请求已过期（未送出）")
                self._ctx.runtime.completed = True
                self._ctx.runtime.complete_reason = "交换请求已过期（未送出）"
                return
            if request.status == "sended" and not request.cancel_reason:
                request.cancel_reason = "等待对方回应超时（5分钟），自动取消"
                request.updated_at = now
                self._request_repo.update(request)

        cancel_reason = getattr(request, "cancel_reason", None)
        if cancel_reason:
            logger.debug(
                "on_start 检测到取消意图: request_id=%s, status=%s, reason=%s",
                request.id,
                request.status,
                cancel_reason,
            )

        if not is_account_past_days(self.account.created_at, 14):
            if is_account_pending_same_day_cooldown(self.account.created_at, 14):
                self._mark_skipped("账号未过14天冷冻期（同日待到期）")
                return
            self._fail_request("账号未过14天冷静期", preserve_last_completed_at=True)
            return

        if request.status == "sending":
            account_card = self._account_card_repo.get(
                self.account.id, request.target_card_id
            )
            if account_card is None or account_card.count < 1:
                self._fail_request("目标卡牌库存不足", preserve_last_completed_at=True)
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
            profile_page_name="profile_page",
            send_text_patterns=get_text_patterns("exchange_send_button"),
            account_id=self.account.id,
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
        """滑动耗尽回调：删除好友关系后失败。"""
        request = self._ctx.runtime.current_request
        if request and self.account.id and request.to_friend_id:
            FriendshipRepository().delete(self.account.id, request.to_friend_id)
            logger.info(
                "好友关系已删除: account=%s, friend_id=%s",
                self.account.id,
                request.to_friend_id,
            )
        return self._fail_and_complete(reason)

    def _preflight_validate(self):
        """任务启动时统一执行前置校验。"""
        if self._ctx.runtime.current_request is None:
            return

        request = self._ctx.runtime.current_request
        rarity_code = (request.target_card_rarity or "").upper()

        if request.status not in {"sending", "sended"}:
            self._fail_request(
                f"请求状态非法: {request.status}",
                preserve_last_completed_at=True,
            )
            return

        if not ExchangeCardService.is_exchangeable(rarity_code):
            self._fail_request("目标稀有度不可交换", preserve_last_completed_at=True)
            return

        if ExchangeCardService.get_required_exchange_points(rarity_code) is None:
            self._fail_request(
                f"不支持的目标稀有度: {rarity_code}",
                preserve_last_completed_at=True,
            )
            return

        if not self._ctx.card.set_code or self._ctx.card.number is None:
            self._fail_request(
                "目标卡牌不存在，无法执行交换",
                preserve_last_completed_at=True,
            )
            return

        if request.status == "sending" and not self._ctx.card.name:
            self._fail_request(
                "目标卡牌名称缺失，无法在确认页核验",
                preserve_last_completed_at=True,
            )
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

    def was_skipped(self) -> bool:
        """任务是否以跳过态收敛。"""
        return self._skipped

    def handle_page(self, page_name: str, page_info: dict) -> ActionResult:
        """按页面分发处理（页面优先，状态判断下沉到各 handler）。"""
        if self._ctx.runtime.current_request is None:
            self._ctx.runtime.completed = True
            return ActionResult.ok(wait=0.2)

        # 恢复重发流程：只有离开“取消完成”页面后才清除恢复标记。
        if (
            self._ctx.runtime.recover_before_send
            and self._is_action_done("recover_cancel_done_clicked")
            and page_name != "exchange_canceled_done_popup"
        ):
            self._ctx.runtime.recover_before_send = False
            logger.info("已退出取消完成页面，进入重发流程")

        # 所有页面 handler 平级注册，不按 status 拦截
        handlers = {
            # 通用入口
            "exchange_locked_popup": self._handle_exchange_locked_popup,
            "home_with_community_icon": self._handle_home,
            "game_home_main": self._handle_home,
            "community_page": self._handle_community,
            "exchange_page_main": self._handle_exchange_page_main,
            # sending 流程页面
            "exchange_choose_friend": self._handle_choose_friend,
            "exchange_select_card": self._handle_select_card,
            "exchange_filter_modal": self._handle_filter_modal,
            "exchange_target_confirm_page": self._handle_target_confirm_page,
            "exchange_confirm_send_popup": self._tap_ok_popup,
            "exchange_confirm_last_popup": self._tap_ok_popup,
            "exchange_proposed_done_popup": self._handle_proposed_done_popup,
            # sended/取消/接受流程页面（全部放开，不限状态）
            "exchange_waiting_page": self._handle_waiting_page,
            "exchange_receive_confirm_page": self._handle_receive_confirm_page,
            "exchange_receive_start_popup": self._handle_receive_start_popup,
            "exchange_swipe_page": self._handle_exchange_swipe_page,
            "exchange_cancel_confirm_popup": self._tap_ok_popup,
            "exchange_canceled_done_popup": self._handle_canceled_done_popup,
        }

        handler = handlers.get(page_name)
        if handler:
            return handler(page_info)

        # 未知页面等待
        return ActionResult.wait(0.6)

    def _handle_home(self, page_info: dict) -> ActionResult:
        """主页进入社群。"""
        return tap_community_icon(self.adb, self.page_detector)

    def _handle_community(self, page_info: dict) -> ActionResult:
        """社群页面进入交换入口。"""
        ocr_results = page_info.get("ocr_results", [])
        result = tap_text_exact(
            self.adb,
            ocr_results,
            get_text_patterns("community_exchange_btn"),
            wait=5,
        )
        return result if result else ActionResult.wait(3)

    def _handle_exchange_page_main(self, page_info: dict) -> ActionResult:
        """交换主页：sending 点击交换，sended 优先点确认，其次点交换进入详情。"""
        if self._ctx.runtime.current_request is None:
            return ActionResult.wait(0.6)
        ocr_results = page_info.get("ocr_results", [])
        request = self._ctx.runtime.current_request
        has_confirm = is_text_visible(
            ocr_results, get_text_patterns("exchange_confirm_button"), exact=False
        )
        has_waiting = is_text_visible(
            ocr_results, get_text_patterns("exchange_waiting_page"), exact=False
        )

        if request.status == "sending" and (has_confirm or has_waiting):
            self._ctx.runtime.recover_before_send = True
            logger.info("sending 阶段检测到已有提议，先走取消链路再重发")
            if has_confirm:
                confirm_result = tap_text_exact(
                    self.adb,
                    ocr_results,
                    get_text_patterns("exchange_confirm_button"),
                    wait=0.8,
                )
                return confirm_result if confirm_result else ActionResult.wait(0.6)
            return ActionResult.wait(0.8)

        if request.status == "sending":
            result = self._tap_exchange_main_button(ocr_results)
            return result if result else ActionResult.wait(0.6)

        if request.status == "sended":
            if has_confirm:
                result = tap_text_exact(
                    self.adb,
                    ocr_results,
                    get_text_patterns("exchange_confirm_button"),
                    wait=0.8,
                )
                return result if result else ActionResult.wait(0.6)

            open_result = self._tap_exchange_main_button(ocr_results)
            if open_result:
                return open_result

            logger.debug("sended 状态暂未识别到入口，等待后重试（避免过早OCR误判）")
            return ActionResult.wait(1.0)

        logger.warning("请求状态不可处理: %s", request.status)
        return ActionResult.wait(0.6)

    def _tap_exchange_main_button(
        self, ocr_results: list[dict]
    ) -> Optional[ActionResult]:
        """交换主页点击最后一个交换文案，避开页头标题。"""
        return tap_text_exact(
            self.adb,
            ocr_results,
            get_text_patterns("exchange_send_button"),
            wait=0.8,
            pick="last",
        )

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

        if self._ctx.friend_flow.friend_verified:
            logger.debug("[选择好友] 已验证，寻找发送按钮")
            send_box = self._friend_helper.find_send_box_by_anchor(ocr_results)
            if send_box:
                return tap_box(self.adb, send_box, wait=1.0)
            in_progress_box = self._friend_helper.find_box_by_anchor(
                ocr_results,
                get_text_patterns("exchange_in_progress"),
            )
            if in_progress_box:
                return self._fail_and_complete("目标好友正在交换中，无法发起交换")
            return self._friend_helper.scroll_or_fail()

        if self._ctx.friend_flow.nickname:
            logger.debug(
                "[选择好友] 有昵称，寻找对应 plus: %s", self._ctx.friend_flow.nickname
            )
            plus_box = self._friend_helper.find_plus_for_nickname(
                ocr_results, self._ctx.friend_flow.nickname
            )
            if plus_box:
                return self._friend_helper.tap_plus_and_wait_profile(plus_box)
            return self._friend_helper.scroll_or_fail()

        if self._ctx.friend_flow.is_in_probe_mode():
            if self._friend_helper.check_scroll_bottom():
                return self._fail_and_complete("已滑到底部，未找到目标好友")
            logger.debug(
                "[选择好友] 探测模式，当前 probe_index=%d, probe_boxes=%d",
                self._ctx.friend_flow.probe_index,
                len(self._ctx.friend_flow.probe_boxes),
            )
            probe_box = self._friend_helper.get_next_probe_box()
            if probe_box:
                return self._friend_helper.tap_plus_and_wait_profile(probe_box)
            logger.debug("[选择好友] 本页探测完成，准备滑动")
            self._ctx.friend_flow.stable_rounds = 0
            return self._friend_helper.scroll_or_fail()

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
            logger.info("点击卡牌后点击 OK")
            ok_result = tap_ok(self.adb, ocr_results, wait=1.0)
            return ok_result if ok_result else ActionResult.wait(0.5)

        if not self._is_action_done("open_filter_clicked"):
            tap_result = tap_template(
                self.adb, self.page_detector, "icon_search", wait=1.0
            )
            if tap_result:
                self._mark_action_done("open_filter_clicked")
                return tap_result

        if not self._is_action_done("filter_applied"):
            return ActionResult.wait(0.6)

        detected = self._card_recognizer.scan(
            set_code=self._ctx.card.set_code,
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
        return result if result else ActionResult.wait(0.6)

    def _tap_ok_popup(self, page_info: dict) -> ActionResult:
        """通用弹窗：点击 OK。"""
        result = tap_ok(self.adb, page_info.get("ocr_results", []), wait=0.8)
        return result if result else ActionResult.wait(0.6)

    def _handle_proposed_done_popup(self, page_info: dict) -> ActionResult:
        """提议完成弹窗：确认后写入 sended，并在当前任务内进入等待窗口。"""
        if self._ctx.runtime.current_request is None:
            return ActionResult.wait(0.6)
        result = tap_ok(self.adb, page_info.get("ocr_results", []), wait=0.8)
        if not result:
            return ActionResult.wait(0.6)

        self._ctx.runtime.current_request.expire_at = None
        self._ctx.runtime.current_request.cancel_reason = None
        self._request_repo.mark_sended(
            self._ctx.runtime.current_request,
            next_check_at=None,
        )
        logger.info("交换已送出，进入 5 分钟等待窗口内持续检查")
        return ActionResult.ok(wait=1.0)

    def _handle_waiting_page(self, page_info: dict) -> ActionResult:
        """等待对方回应页面：窗口内持续轮询，超时后走取消链路。"""
        if self._ctx.runtime.current_request is None:
            return ActionResult.wait(0.6)
        now = datetime.now()

        request = self._ctx.runtime.current_request
        cancel_reason = request.cancel_reason
        cancel_mode = self._ctx.runtime.recover_before_send or bool(cancel_reason)
        logger.debug(
            "[waiting_page] cancel_mode=%s, recover=%s, cancel_reason=%s, action_done=%s",
            cancel_mode,
            self._ctx.runtime.recover_before_send,
            cancel_reason,
            self._is_action_done("waiting_cancel_clicked"),
        )
        if cancel_mode:
            if not self._is_action_done("waiting_cancel_clicked"):
                cancel_result = tap_text_exact(
                    self.adb,
                    page_info.get("ocr_results", []),
                    get_text_patterns("exchange_cancel_button"),
                    wait=0.8,
                )
                logger.info("[waiting_page] 点击取消结果: %s", bool(cancel_result))
                if cancel_result:
                    self._mark_action_done("waiting_cancel_clicked")
                    return cancel_result
                else:
                    logger.warning("[waiting_page] 取消模式但点击失败，继续等待")
            return ActionResult.wait(0.6)

        if not self._is_action_done("waiting_window_started"):
            request.expire_at = now + timedelta(seconds=EXCHANGE_WINDOW_SECONDS)
            request.updated_at = now
            self._request_repo.update(request)
            self._mark_action_done("waiting_window_started")
            logger.info(
                "进入等待页，启动5分钟交换窗口: request_id=%s, expire_at=%s",
                request.id,
                request.expire_at,
            )

        if (
            not cancel_reason
            and request.expire_at is not None
            and now >= request.expire_at
        ):
            request.cancel_reason = "等待对方回应超时（5分钟），自动取消"
            request.updated_at = now
            self._request_repo.update(request)
            cancel_reason = request.cancel_reason
            logger.info("等待窗口超时，开始取消交换: request_id=%s", request.id)

        if cancel_reason:
            return ActionResult.wait(0.6)

        refresh_result = tap_template(
            self.adb, self.page_detector, "btn_close", wait=0.8
        )
        if refresh_result:
            logger.info("等待窗口轮询：返回交换主页后重新点击确认刷新状态")
            return refresh_result
        return ActionResult.wait(1.0)

    def _handle_receive_confirm_page(self, page_info: dict) -> ActionResult:
        """对方已回应页面：确认交换或拒绝。"""
        if self._ctx.runtime.current_request is None:
            return ActionResult.wait(0.6)
        ocr_results = page_info.get("ocr_results", [])

        if self._ctx.runtime.current_request.cancel_reason:
            logger.debug(
                "确认页执行拒绝分支: request_id=%s, reason=%s",
                self._ctx.runtime.current_request.id,
                self._ctx.runtime.current_request.cancel_reason,
            )
            reject_result = tap_text_exact(
                self.adb,
                ocr_results,
                get_text_patterns("exchange_reject_button"),
                wait=0.8,
            )
            return reject_result if reject_result else ActionResult.wait(0.6)

        exchange_result = tap_text_exact(
            self.adb,
            ocr_results,
            get_text_patterns("exchange_send_button"),
            wait=0.8,
        )
        return exchange_result if exchange_result else ActionResult.wait(0.6)

    def _handle_receive_start_popup(self, page_info: dict) -> ActionResult:
        """开始交换确认弹窗：点击 OK 后进入滑卡完成页。"""
        if self._ctx.runtime.current_request is None:
            return ActionResult.wait(0.6)
        result = tap_ok(self.adb, page_info.get("ocr_results", []), wait=0.8)
        if not result:
            return ActionResult.wait(0.6)
        return ActionResult.ok(wait=0.8)

    def _handle_exchange_swipe_page(self, page_info: dict) -> ActionResult:
        """交换完成滑卡页：上滑后再落库 completed。"""
        if self._ctx.runtime.current_request is None:
            return ActionResult.wait(0.6)
        if self._is_action_done("exchange_swiped"):
            return ActionResult.ok(wait=0.5)

        swipe_result = swipe_card_register(self.adb, wait=1.0)
        if not swipe_result.success:
            return swipe_result

        self._mark_action_done("exchange_swiped")
        self._finalize_exchange_success()
        self._ctx.runtime.completed = True
        self._ctx.runtime.complete_reason = "交换完成"
        return ActionResult.ok(wait=0.8)

    def _finalize_exchange_success(self):
        """交换成功后同步请求状态与发送方库存。"""
        request = self._ctx.runtime.current_request
        if request is None:
            return

        self._request_repo.mark_completed(request)

        if self.account.id is None:
            return
        card_id = request.target_card_id
        if card_id is None:
            return

        row = self._account_card_repo.get(self.account.id, card_id)
        if row is None:
            return

        new_count = max(int(row.count) - 1, 0)
        self._account_card_repo.upsert(
            account_id=self.account.id,
            card_id=card_id,
            count=new_count,
            yolo_conf=getattr(row, "yolo_conf", None),
            hash_similarity=getattr(row, "hash_similarity", None),
        )

    def _handle_canceled_done_popup(self, page_info: dict) -> ActionResult:
        """取消完成弹窗：点击 OK 并落库 canceled。"""
        if self._ctx.runtime.current_request is None:
            return ActionResult.wait(0.6)
        result = tap_ok(self.adb, page_info.get("ocr_results", []), wait=0.8)
        if not result:
            return ActionResult.wait(0.6)

        if self._ctx.runtime.recover_before_send:
            if not self._is_action_done("recover_cancel_done_clicked"):
                self._ctx.runtime.current_request.cancel_reason = None
                self._ctx.runtime.current_request.expire_at = None
                self._ctx.runtime.current_request.next_check_at = None
                self._ctx.runtime.current_request.updated_at = datetime.now()
                self._request_repo.update(self._ctx.runtime.current_request)
                self._mark_action_done("recover_cancel_done_clicked")
                logger.info("旧提议已取消，等待页面退出后继续重发")
            else:
                logger.info("取消完成页仍停留，继续点击 OK 等待退出")
            return ActionResult.ok(wait=1.0)

        reason = self._ctx.runtime.current_request.cancel_reason or "交换已取消"
        if "超时" in reason:
            self._request_repo.mark_failed(self._ctx.runtime.current_request, reason)
            self._ctx.runtime.complete_reason = "交换超时失败"
        else:
            self._request_repo.mark_canceled(
                self._ctx.runtime.current_request, reason=reason
            )
            self._ctx.runtime.complete_reason = "交换已取消"
        self._ctx.runtime.completed = True
        return result

    def _mark_skipped(self, reason: str):
        """将当前任务标记为跳过并结束。"""
        self._skipped = True
        self._skip_reason = reason
        self._ctx.runtime.completed = True
        self._ctx.runtime.complete_reason = reason

    def _handle_exchange_locked_popup(self, page_info: dict) -> ActionResult:
        """交换功能未解锁弹窗：点击 OK 并跳过。"""
        result = tap_ok(self.adb, page_info.get("ocr_results", []), wait=0.8)
        if not result:
            return ActionResult.wait(0.6)
        self._mark_skipped("交换功能未解锁（14天冷冻期未到）")
        return result

    def _fail_request(self, reason: str, preserve_last_completed_at: bool = False):
        """将当前请求标记失败并结束任务。"""
        if self._ctx.runtime.current_request is not None:
            self._request_repo.mark_failed(self._ctx.runtime.current_request, reason)
        if preserve_last_completed_at:
            self.mark_completed_without_timestamp(reason)
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
