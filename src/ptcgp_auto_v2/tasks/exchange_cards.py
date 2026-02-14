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
)
from ptcgp_auto_v2.hooks import ExchangeDelayPostHook
from ptcgp_auto_v2.hooks.friend_hooks import FriendPreHook
from ptcgp_auto_v2.infra.card_hash_manager import get_card_hash_manager
from ptcgp_auto_v2.infra.icon_group_detector import IconGroupDetector
from ptcgp_auto_v2.infra.model_manager import get_model_manager
from ptcgp_auto_v2.infra.yolo_card_recognizer import YoloCardRecognizer
from ptcgp_auto_v2.locales import get_text_patterns
from ptcgp_auto_v2.services import ExchangeCardService
from ptcgp_auto_v2.tasks.utils.friend_id_utils import extract_friend_id_from_text
from ptcgp_auto_v2.tasks.utils.rarity_filter import (
    select_rarity_in_filter_panel,
)
from ptcgp_auto_v2.tasks.utils.constants import (
    BASE_CARD_SCROLL_DISTANCE_Y,
    BASE_FRIEND_ROW_THRESHOLD_Y,
    BASE_FRIEND_SCROLL_DISTANCE_Y,
    MAX_CARD_STABLE_ROUNDS,
    MAX_FRIEND_PROFILE_READ_ROUNDS,
    MAX_FRIEND_SCROLL_ROUNDS,
    MAX_FRIEND_STABLE_ROUNDS,
)
from ptcgp_auto_v2.tasks.utils.friend_card_flow import (
    build_detect_signature,
    build_ocr_signature,
    find_send_button_for_target,
    find_target_search_plus_box,
)
from ptcgp_auto_v2.utils.account_cooldown import is_account_past_days
from ptcgp_auto_v2.utils.card_name_resolver import resolve_card_name
from ptcgp_auto_v2.utils.gesture import (
    click_close,
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


@dataclass
class ExchangeRuntimeState:
    """任务运行态。"""

    current_request: Optional[ExchangeCardRequest] = None
    completed: bool = False
    complete_reason: Optional[str] = None
    delay_seconds: Optional[float] = None
    delay_reason: Optional[str] = None


@dataclass
class ExchangeTargetState:
    """请求目标态。"""

    nickname: Optional[str] = None
    card_name: Optional[str] = None
    card_set_code: Optional[str] = None
    card_number: Optional[int] = None
    friend_verified: bool = False


@dataclass
class ExchangeFlowState:
    """页面流程态。"""

    friend_scroll_rounds: int = 0
    friend_stable_rounds: int = 0
    friend_profile_read_rounds: int = 0
    card_stable_rounds: int = 0
    last_friend_signature: Optional[str] = None
    last_card_signature: Optional[str] = None
    action_cache: dict[str, bool] = field(default_factory=dict)


@dataclass
class ExchangeTaskContext:
    """交换任务上下文：按语义归类状态。"""

    runtime: ExchangeRuntimeState = field(default_factory=ExchangeRuntimeState)
    target: ExchangeTargetState = field(default_factory=ExchangeTargetState)
    flow: ExchangeFlowState = field(default_factory=ExchangeFlowState)

    def reset(self):
        """重置任务上下文。"""
        self.runtime = ExchangeRuntimeState()
        self.target = ExchangeTargetState()
        self.flow = ExchangeFlowState()


# 交换特有常量
RECHECK_DELAY_SECONDS = 300  # sended 阶段延时复查秒数（5分钟）


def _build_exchange_pages() -> list[dict]:
    """构建交换任务页面识别规则。

    需求原文：进来游戏，主页，通过模板匹配「icon_community」点击进入到社群页面。
    """
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
            "priority": 30,
        },
        {
            "name": "exchange_page_main",
            "identifiers": get_text_patterns("exchange_page"),
            "match_all": True,
            "priority": 40,
        },
        {
            "name": "exchange_choose_friend",
            "identifiers": get_text_patterns("exchange_choose_friend_title"),
            "match_all": True,
            "priority": 50,
        },
        {
            "name": "exchange_friend_profile",
            "identifiers": get_text_patterns("exchange_friend_profile"),
            "match_all": True,
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

    def on_start(self):
        """加载请求并执行前置校验。"""
        self._ctx.reset()

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
            self._ctx.target.nickname = request_nickname

        card = self._card_repo.get_by_id(request.target_card_id)
        if card is not None:
            self._ctx.target.card_name = resolve_card_name(
                self._card_repo,
                card.set_code,
                card.number,
            )
            self._ctx.target.card_set_code = card.set_code
            self._ctx.target.card_number = card.number

        self._preflight_validate()

    def _preflight_validate(self):
        """任务启动时统一执行前置校验并在失败时收敛。"""
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

        if not self._ctx.target.nickname:
            self._fail_request("目标昵称缺失，请先完成加好友并抓取昵称")
            return

        if not self._ctx.target.card_set_code or self._ctx.target.card_number is None:
            self._fail_request("目标卡牌不存在，无法执行交换")
            return

        if request.status == "sending" and not self._ctx.target.card_name:
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
                target_nickname=self._ctx.target.nickname,
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
        if page_name == "exchange_page_main":
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
            "exchange_friend_profile": self._handle_friend_profile,
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
        if self._ctx.runtime.current_request.status == "sending":
            result = tap_text_exact(
                self.adb,
                ocr_results,
                get_text_patterns("exchange_send_button"),
                wait=0.8,
            )
            return result or ActionResult.wait(0.6)

        result = tap_text_exact(
            self.adb,
            ocr_results,
            get_text_patterns("exchange_confirm_button"),
            wait=0.8,
        )
        return result or ActionResult.wait(0.6)

    def _handle_choose_friend(self, page_info: dict) -> ActionResult:
        """请选择朋友页面：先核验 friend_id，再点击对应交换。"""
        if self._ctx.runtime.current_request is None:
            return ActionResult.wait(0.6)
        ocr_results = page_info.get("ocr_results", [])

        signature = build_ocr_signature(ocr_results)
        if signature == self._ctx.flow.last_friend_signature:
            self._ctx.flow.friend_stable_rounds += 1
        else:
            self._ctx.flow.friend_stable_rounds = 0
            self._ctx.flow.last_friend_signature = signature

        if not self._ctx.target.friend_verified:
            if not self._is_action_done("friend_plus_clicked"):
                plus_box = self._find_target_search_plus_box(ocr_results)
                if plus_box:
                    self._mark_action_done("friend_plus_clicked")
                    return tap_box(self.adb, plus_box, wait=1.0)
            return self._continue_find_target_in_friend_list()

        exchange_box = self._find_exchange_box_for_verified_target(ocr_results)
        if exchange_box:
            return tap_box(self.adb, exchange_box, wait=1.0)
        return self._continue_find_target_in_friend_list()

    def _continue_find_target_in_friend_list(self) -> ActionResult:
        """好友列表持续查找目标。"""
        if self._ctx.flow.friend_stable_rounds >= MAX_FRIEND_STABLE_ROUNDS:
            return self._fail_and_complete("好友列表疑似到底且未找到目标账号")

        self._ctx.flow.friend_scroll_rounds += 1
        if self._ctx.flow.friend_scroll_rounds > MAX_FRIEND_SCROLL_ROUNDS:
            return self._fail_and_complete("好友列表遍历达到上限，未定位到目标账号")

        start, end = scroll_points(
            self.adb,
            base_distance_y=BASE_FRIEND_SCROLL_DISTANCE_Y,
            direction="up",
        )
        swipe(self.adb, start, end, wait=0.9)
        return ActionResult.ok(wait=0.8)

    def _handle_friend_profile(self, page_info: dict) -> ActionResult:
        """好友详情页：提取 friend_id 核验后关闭返回。"""
        if self._ctx.runtime.current_request is None:
            return ActionResult.wait(0.6)

        ocr_results = page_info.get("ocr_results", [])
        extracted_friend_id: Optional[str] = None
        for item in ocr_results:
            extracted_friend_id = extract_friend_id_from_text(str(item.get("text", "")))
            if extracted_friend_id:
                break

        if not extracted_friend_id:
            self._ctx.flow.friend_profile_read_rounds += 1
            if (
                self._ctx.flow.friend_profile_read_rounds
                < MAX_FRIEND_PROFILE_READ_ROUNDS
            ):
                return ActionResult.wait(0.6)
            self._ctx.flow.action_cache.pop("friend_plus_clicked", None)
        elif extracted_friend_id == (
            self._ctx.runtime.current_request.to_friend_id or ""
        ):
            self._ctx.target.friend_verified = True
            self._ctx.flow.action_cache.pop("friend_plus_clicked", None)
        else:
            self._ctx.target.friend_verified = False
            self._ctx.flow.action_cache.pop("friend_plus_clicked", None)

        self._ctx.flow.friend_profile_read_rounds = 0
        close_result = click_close(
            self.adb,
            self.page_detector,
            ocr_results,
            get_text_patterns("text_x"),
        )
        return close_result or ActionResult.wait(0.8)

    def _handle_select_card(self, page_info: dict) -> ActionResult:
        """选卡页面：筛选稀有度，扫描目标卡并点击。"""
        if self._ctx.runtime.current_request is None:
            return ActionResult.wait(0.6)
        ocr_results = page_info.get("ocr_results", [])

        if self._is_action_done("target_card_tapped") and is_text_visible(
            ocr_results,
            get_text_patterns("exchange_insufficient_points"),
            exact=False,
        ):
            return self._fail_and_complete("点击目标卡后检测到交换点数不足")

        if not self._is_action_done("open_filter_clicked"):
            result = tap_template(self.adb, self.page_detector, "icon_search", wait=1.0)
            if result:
                self._mark_action_done("open_filter_clicked")
                return result

        if not self._is_action_done("filter_applied"):
            return ActionResult.wait(0.6)

        detected = self._card_recognizer.scan(
            set_code=self._ctx.target.card_set_code,
            debug=False,
        )
        tap_result = self._tap_target_card_by_scan(detected)
        if tap_result:
            self._ctx.flow.card_stable_rounds = 0
            self._ctx.flow.last_card_signature = None
            self._mark_action_done("target_card_tapped")
            return tap_result

        card_signature = build_detect_signature(detected)
        if card_signature == self._ctx.flow.last_card_signature:
            self._ctx.flow.card_stable_rounds += 1
        else:
            self._ctx.flow.card_stable_rounds = 0
            self._ctx.flow.last_card_signature = card_signature

        if self._ctx.flow.card_stable_rounds >= MAX_CARD_STABLE_ROUNDS:
            return self._fail_and_complete("连续三次扫描未找到目标卡牌")

        start, end = scroll_points(
            self.adb,
            base_distance_y=BASE_CARD_SCROLL_DISTANCE_Y,
            direction="up",
        )
        swipe(self.adb, start, end, wait=0.8)
        return ActionResult.ok(wait=0.6)

    def _handle_filter_modal(self, page_info: dict) -> ActionResult:
        """筛选弹窗：按目标稀有度选择后点击 OK。"""
        if self._ctx.runtime.current_request is None:
            return ActionResult.wait(0.6)
        ocr_results = page_info.get("ocr_results", [])

        if not self._is_action_done("rarity_selected"):
            result = self._select_target_rarity_group(page_info)
            if result:
                self._mark_action_done("rarity_selected")
                return result

        ok_result = tap_ok(self.adb, ocr_results, wait=1.0)
        if ok_result:
            self._mark_action_done("filter_applied")
            return ok_result
        return ActionResult.wait(0.6)

    def _handle_target_confirm_page(self, page_info: dict) -> ActionResult:
        """送卡确认页面：校验目标昵称后点击 OK。"""
        if self._ctx.runtime.current_request is None:
            return ActionResult.wait(0.6)
        ocr_results = page_info.get("ocr_results", [])

        if self._ctx.target.nickname and not is_text_visible(
            ocr_results,
            [self._ctx.target.nickname],
            exact=False,
        ):
            return self._fail_and_complete("确认页目标昵称不匹配")

        if self._ctx.target.card_name and not is_text_visible(
            ocr_results,
            [self._ctx.target.card_name],
            exact=False,
        ):
            logger.info("确认页未识别到目标卡名，继续尝试按流程确认")

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
        self._ctx.flow.action_cache[action_name] = True

    def _is_action_done(self, action_name: str) -> bool:
        """查询页面动作是否完成。"""
        return self._ctx.flow.action_cache.get(action_name, False)

    def _find_target_search_plus_box(
        self, ocr_results: list[dict]
    ) -> Optional[tuple[int, int, int, int]]:
        """在好友列表中查找目标昵称对应的 icon_search_plus。"""
        if not hasattr(self.page_detector, "find_all_templates"):
            return None

        matches = self.page_detector.find_all_templates(
            "icon_search_plus",
            threshold=0.8,
            scale=1.0,
        )
        plus_boxes: list[tuple[int, int, int, int]] = []
        for match in matches:
            box = getattr(match, "box", None)
            if box and len(box) == 4:
                plus_boxes.append(tuple(box))

        if not plus_boxes or not self._ctx.target.nickname:
            return None

        row_threshold_y = self.adb.scaled_y(BASE_FRIEND_ROW_THRESHOLD_Y)
        return find_target_search_plus_box(
            ocr_results=ocr_results,
            target_nickname=self._ctx.target.nickname,
            search_plus_boxes=plus_boxes,
            row_threshold_y=row_threshold_y,
        )

    def _find_exchange_box_for_verified_target(
        self, ocr_results: list[dict]
    ) -> Optional[tuple[int, int, int, int]]:
        """在好友列表中定位目标行的交换按钮。"""
        if not self._ctx.target.nickname:
            return None
        return find_send_button_for_target(
            ocr_results=ocr_results,
            target_nickname=self._ctx.target.nickname,
            send_text_patterns=get_text_patterns("exchange_send_button"),
        )

    def _select_target_rarity_group(self, page_info: dict) -> Optional[ActionResult]:
        """在筛选弹窗中按目标稀有度点选图标分组。"""
        if self._ctx.runtime.current_request is None:
            return None
        rarity_code = (
            self._ctx.runtime.current_request.target_card_rarity or ""
        ).upper()
        return select_rarity_in_filter_panel(
            adb=self.adb,
            page_detector=self.page_detector,
            icon_detector=self._icon_detector,
            rarity_code=rarity_code,
            wait=0.4,
        )

    def _tap_target_card_by_scan(self, detected) -> Optional[ActionResult]:
        """通过 YOLO+Hash 扫描定位目标卡牌。"""
        if not detected:
            return None
        if (
            self._ctx.target.card_set_code is None
            or self._ctx.target.card_number is None
        ):
            return None

        candidates = [
            item
            for item in detected
            if item.set_code == self._ctx.target.card_set_code
            and item.card_number == self._ctx.target.card_number
        ]
        if not candidates:
            return None

        best = max(candidates, key=lambda item: (item.similarity, item.confidence))
        return tap(self.adb, int(best.center[0]), int(best.center[1]), wait=0.8)
