# -*- coding: utf-8 -*-
"""交换卡牌任务。

按 ExchangeCardRequest 状态机执行 sending / sended 两阶段流程。
任务本身始终收敛为完成态，业务失败写入 request。
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Optional, cast

from ptcgp_auto_v2.core.task_base import ActionResult, ResetType, TaskRegistry
from ptcgp_auto_v2.core.stateful_task import StatefulTask
from ptcgp_auto_v2.db.engine import session_scope
from ptcgp_auto_v2.db.repositories.factory import RepositoryFactory
from ptcgp_auto_v2.db.repositories.exchange_card_request_repository import (
    ExchangeCardRequestRepository,
    ExchangeCardRequestSnapshot,
)
from ptcgp_auto_v2.db.repositories import (
    AccountCardRepository,
    CardRepository,
    FriendshipRepository,
)
from ptcgp_auto_v2.hooks import ExchangeDelayPostHook
from ptcgp_auto_v2.infra.adb import ScreenshotMode
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

# 交换等待窗口秒数：送出提议后最多等待 5 分钟。
EXCHANGE_WINDOW_SECONDS = 300


def _build_exchange_pages() -> list[dict]:
    """构建交换任务页面识别规则。"""
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
class ExchangeCardsTask(StatefulTask):
    """交换卡牌任务。"""

    task_type = "exchange_cards"
    reset_type = ResetType.ONCE
    pages = _build_exchange_pages()
    max_same_page_rounds = 20
    max_iterations = 100
    screenshot_ocr_mode = ScreenshotMode.DISPLAY_RAW

    def __init__(self, adb, recognizer, page_detector):
        super().__init__(adb, recognizer, page_detector)
        self._icon_detector = IconGroupDetector()
        self._card_recognizer = YoloCardRecognizer(
            adb=adb,
            model_manager=get_model_manager(),
            hash_manager=get_card_hash_manager(),
        )
        self._card_stable_rounds = 0
        self._last_card_signature: Optional[str] = None
        self._filter_state = FilterPanelState()
        self._friend_helper: Optional[FriendSelectionHelper] = None

    def _req(self) -> Optional[ExchangeCardRequestSnapshot]:
        """获取当前请求。"""
        return cast(Optional[ExchangeCardRequestSnapshot], self.state_get("request"))

    def _friend_flow(self) -> FriendSelectionFlow:
        """获取好友选择流程状态。"""
        return cast(FriendSelectionFlow, self.state_get("friend_flow"))

    def _update_request_fields(self, request_id: int, **fields):
        """按 ID 更新交换请求字段。"""
        with session_scope() as session:
            if not ExchangeCardRequestRepository(session).update_fields_by_id(
                request_id, **fields
            ):
                raise RuntimeError(f"交换请求更新失败: request_id={request_id}")

    def _done(self, reason: str = "", skip: bool = False):
        """按原语义收敛任务。"""
        if skip:
            self.skip(reason)
        else:
            self.complete(reason)

    def on_start(self):
        """加载请求并执行前置校验。"""
        self.state.reset()
        self._card_stable_rounds = 0
        self._last_card_signature = None
        self._filter_state = FilterPanelState()

        if self.account.id is None:
            self.mark_completed_without_timestamp("账号ID为空")
            self._done("账号ID为空")
            return

        with session_scope() as session:
            request_repo = ExchangeCardRequestRepository(session)
            request = request_repo.get_active_by_account_data(self.account.id)
        if request is None:
            self.mark_completed_without_timestamp("无活跃交换请求")
            self._done("无活跃交换请求")
            return

        now = datetime.now()
        if request.expire_at and now >= request.expire_at:
            if request.status == "sending":
                with session_scope() as session:
                    if not ExchangeCardRequestRepository(session).mark_canceled(
                        request.id, reason="交换请求已过期（未送出）"
                    ):
                        raise RuntimeError(
                            f"交换请求过期取消失败: request_id={request.id}"
                        )
                self.mark_completed_without_timestamp("交换请求已过期（未送出）")
                self._done("交换请求已过期（未送出）")
                return
            if request.status == "sended" and not request.cancel_reason:
                request.cancel_reason = "等待对方回应超时（5分钟），自动取消"
                request.updated_at = now
                with session_scope() as session:
                    if not ExchangeCardRequestRepository(session).set_cancel_reason(
                        request.id, request.cancel_reason
                    ):
                        raise RuntimeError(
                            f"交换请求取消原因更新失败: request_id={request.id}"
                        )

        if request.cancel_reason:
            logger.debug(
                "on_start 检测到取消意图: request_id=%s, status=%s",
                request.id,
                request.status,
            )

        if not is_account_past_days(self.account.created_at, 14):
            if is_account_pending_same_day_cooldown(self.account.created_at, 14):
                return self._done("账号未过14天冷冻期（同日待到期）", skip=True)
            return self._fail("账号未过14天冷静期", preserve_last_completed_at=True)

        if request.status == "sending":
            with session_scope() as session:
                account_card_repo = AccountCardRepository(session)
                account_card = account_card_repo.get(
                    self.account.id, request.target_card_id
                )
                account_card_count = int(account_card.count) if account_card else 0
            if account_card_count < 1:
                return self._fail("目标卡牌库存不足", preserve_last_completed_at=True)

        with session_scope() as session:
            card_repo = CardRepository(session)
            card = card_repo.get_by_id(request.target_card_id)
        rarity_code = (request.target_card_rarity or "").upper()

        if request.status not in {"sending", "sended"}:
            return self._fail(
                f"请求状态非法: {request.status}", preserve_last_completed_at=True
            )
        if not ExchangeCardService.is_exchangeable(rarity_code):
            return self._fail("目标稀有度不可交换", preserve_last_completed_at=True)
        if ExchangeCardService.get_required_exchange_points(rarity_code) is None:
            return self._fail(
                f"不支持的目标稀有度: {rarity_code}", preserve_last_completed_at=True
            )
        if card is None:
            return self._fail(
                "目标卡牌不存在，无法执行交换", preserve_last_completed_at=True
            )
        if request.status == "sending" and not card.name:
            return self._fail(
                "目标卡牌名称缺失，无法在确认页核验", preserve_last_completed_at=True
            )

        nickname = getattr(request, "to_nickname", None)
        if not nickname:
            with session_scope() as session:
                friendship_repo = FriendshipRepository(session)
                friendship = friendship_repo.get_friendship(
                    self.account.id, request.to_friend_id
                )
                friendship_nickname = (
                    friendship.friend_nickname if friendship else None
                )
            if friendship_nickname:
                nickname = friendship_nickname
                logger.info(
                    "从好友关系读取昵称: %s -> %s", request.to_friend_id, nickname
                )

        self.state_update(
            {
                "request": request,
                "recover": False,
                "card_set_code": card.set_code,
                "card_number": card.number,
                "friend_nickname": nickname,
                "friend_flow": FriendSelectionFlow(nickname=nickname),
                "filter_action_cache": {},
            }
        )

        self._init_friend_helper()

    def _init_friend_helper(self):
        """初始化好友选择辅助类。"""
        request = self._req()
        if request is None:
            return

        self._friend_helper = FriendSelectionHelper(
            adb=self.adb,
            page_detector=self.page_detector,
            flow=self._friend_flow(),
            target_friend_id=request.to_friend_id or "",
            profile_page_name="profile_page",
            send_text_patterns=get_text_patterns("exchange_send_button"),
            account_id=self.account.id,
            on_nickname_found=self._on_nickname_found,
            on_scroll_exhausted=self._on_scroll_exhausted,
        )

    def _on_nickname_found(self, account_id: int, friend_id: str, nickname: str):
        """发现 nickname 回调：持久化并同步运行态。"""
        with session_scope() as session:
            friendship_repo = FriendshipRepository(session)
            if not friendship_repo.update_nickname(
                account_id=account_id,
                friend_id=friend_id,
                nickname=nickname,
            ):
                raise RuntimeError(
                    f"好友昵称更新失败: account_id={account_id}, friend_id={friend_id}"
                )
        self.state_set("friend_nickname", nickname)

    def _on_scroll_exhausted(self, reason: str) -> ActionResult:
        """滑动耗尽回调：删除好友关系后失败。"""
        request = self._req()
        if request and self.account.id and request.to_friend_id:
            with session_scope() as session:
                friendship_repo = FriendshipRepository(session)
                friendship_repo.delete(self.account.id, request.to_friend_id)
            logger.info(
                "好友关系已删除: account=%s, friend_id=%s",
                self.account.id,
                request.to_friend_id,
            )
        return self._fail(reason)

    def get_pre_hooks(self) -> list:
        """前置 Hook：确保好友关系。"""
        request = self._req()
        if self.is_completed() or request is None:
            return []
        target_friend_id = (request.to_friend_id or "").strip()
        if not target_friend_id:
            return []
        return [
            FriendPreHook(
                target_friend_id=target_friend_id,
                target_account_id=request.to_account_id,
                target_nickname=cast(Optional[str], self.state_get("friend_nickname")),
            )
        ]

    def get_post_hooks(self) -> list:
        """返回交换任务后置 Hook。"""
        return [ExchangeDelayPostHook()]

    def handle_page(self, page_name: str, page_info: dict) -> ActionResult:
        """补充恢复状态切换后交给基类纯分发。"""
        request = self._req()
        if request is None:
            self._done()
            return ActionResult.ok(wait=0.2)

        if (
            self.state_get("recover")
            and self.is_action_done("recover_clicked")
            and page_name != "exchange_canceled_done_popup"
        ):
            self.state_set("recover", False)
            logger.info("已退出取消完成页面，进入重发流程")

        return super().handle_page(page_name, page_info)

    def handle_unmapped_page(self, page_name: str, page_info: dict) -> ActionResult:
        """未映射页面统一等待。"""
        return ActionResult.wait(0.6)

    def _handle_home(self, page_info: dict) -> ActionResult:
        """主页点击社群入口。"""
        return tap_community_icon(self.adb, self.page_detector)

    _handle_home_with_community_icon = _handle_game_home_main = _handle_home

    def _handle_community_page(self, page_info: dict) -> ActionResult:
        """社群页面进入交换入口。"""
        result = tap_text_exact(
            self.adb,
            page_info.get("ocr_results", []),
            get_text_patterns("community_exchange_btn"),
            wait=5,
        )
        return result or ActionResult.wait(3)

    def _handle_exchange_page_main(self, page_info: dict) -> ActionResult:
        """交换主页：sending 点击交换，sended 优先点确认，其次点交换进入详情。"""
        request = self._req()
        if request is None:
            return ActionResult.wait(0.6)

        ocr = page_info.get("ocr_results", [])
        has_confirm = is_text_visible(
            ocr, get_text_patterns("exchange_confirm_button"), exact=False
        )
        has_waiting = is_text_visible(
            ocr, get_text_patterns("exchange_waiting_page"), exact=False
        )

        if request.status == "sending" and (has_confirm or has_waiting):
            self.state_set("recover", True)
            logger.info("sending 阶段检测到已有提议，先走取消链路再重发")
            if has_confirm:
                return tap_text_exact(
                    self.adb,
                    ocr,
                    get_text_patterns("exchange_confirm_button"),
                    wait=0.8,
                ) or ActionResult.wait(0.6)
            return ActionResult.wait(0.8)

        if request.status == "sending":
            return tap_text_exact(
                self.adb,
                ocr,
                get_text_patterns("exchange_send_button"),
                wait=0.8,
                pick="last",
            ) or ActionResult.wait(0.6)

        if request.status == "sended":
            if has_confirm:
                return tap_text_exact(
                    self.adb,
                    ocr,
                    get_text_patterns("exchange_confirm_button"),
                    wait=0.8,
                ) or ActionResult.wait(0.6)
            result = tap_text_exact(
                self.adb,
                ocr,
                get_text_patterns("exchange_send_button"),
                wait=0.8,
                pick="last",
            )
            if result:
                return result
            logger.debug("sended 状态暂未识别到入口，等待后重试")
            return ActionResult.wait(1.0)

        return ActionResult.wait(0.6)

    def _handle_exchange_choose_friend(self, page_info: dict) -> ActionResult:
        """请选择朋友页面：先核验 friend_id，再点击对应交换。"""
        request = self._req()
        if self._friend_helper is None or request is None:
            return ActionResult.wait(0.6)

        ocr = page_info.get("ocr_results", [])
        friend_flow = self._friend_flow()

        if is_text_visible(
            ocr, get_text_patterns("gift_choose_friend_empty"), exact=False
        ):
            return self._fail("好友列表为空，无法执行交换")

        if friend_flow.friend_verified:
            send_box = self._friend_helper.find_send_box_by_anchor(ocr)
            if send_box:
                return tap_box(self.adb, send_box, wait=1.0)
            if self._friend_helper.find_box_by_anchor(
                ocr, get_text_patterns("exchange_in_progress")
            ):
                return self._fail("目标好友正在交换中，无法发起交换")
            return self._friend_helper.scroll_or_fail()

        nickname = cast(Optional[str], self.state_get("friend_nickname"))
        if nickname:
            plus_box = self._friend_helper.find_plus_for_nickname(ocr, nickname)
            if plus_box:
                return self._friend_helper.tap_plus_and_wait_profile(plus_box)
            return self._friend_helper.scroll_or_fail()

        if friend_flow.is_in_probe_mode():
            if self._friend_helper.check_scroll_bottom():
                return self._fail("已滑到底部，未找到目标好友")
            probe_box = self._friend_helper.get_next_probe_box()
            if probe_box:
                return self._friend_helper.tap_plus_and_wait_profile(probe_box)
            friend_flow.stable_rounds = 0
            return self._friend_helper.scroll_or_fail()

        return self._friend_helper.scroll_or_fail()

    def _handle_exchange_select_card(self, page_info: dict) -> ActionResult:
        """选卡页面：筛选稀有度，扫描目标卡并点击。"""
        if self._req() is None:
            return ActionResult.wait(0.6)

        ocr = page_info.get("ocr_results", [])

        if self.is_action_done("card_tapped"):
            if is_text_visible(
                ocr, get_text_patterns("exchange_insufficient_points"), exact=False
            ):
                return self._fail("点击目标卡后检测到交换点数不足")
            return tap_ok(self.adb, ocr, wait=1.0) or ActionResult.wait(0.5)

        if not self.is_action_done("filter_opened"):
            result = tap_template(self.adb, self.page_detector, "icon_search", wait=1.0)
            if result:
                self.mark_action_done("filter_opened")
                return result

        if not self.is_action_done("filter_applied"):
            return ActionResult.wait(0.6)

        set_code = cast(Optional[str], self.state_get("card_set_code"))
        detected = self._card_recognizer.scan(set_code=set_code)
        tap_result = self._tap_target_card(detected)
        if tap_result:
            self._card_stable_rounds = 0
            self._last_card_signature = None
            self.mark_action_done("card_tapped")
            logger.info("点击目标卡牌: set_code=%s", set_code)
            return tap_result

        sig = build_detect_signature(detected)
        if sig == self._last_card_signature:
            self._card_stable_rounds += 1
        else:
            self._card_stable_rounds = 0
            self._last_card_signature = sig

        if self._card_stable_rounds >= MAX_CARD_STABLE_ROUNDS:
            return self._fail("连续三次扫描未找到目标卡牌")

        start, end = scroll_points(
            self.adb, base_distance_y=BASE_CARD_SCROLL_DISTANCE_Y, direction="up"
        )
        swipe(self.adb, start, end, wait=0.8)
        return ActionResult.ok(wait=0.6)

    def _handle_exchange_filter_modal(self, page_info: dict) -> ActionResult:
        """筛选弹窗按目标稀有度执行筛选。"""
        request = self._req()
        if request is None:
            return ActionResult.wait(0.6)

        rarity_code = (request.target_card_rarity or "").upper()
        filter_action_cache = cast(dict[str, bool], self.state_get("filter_action_cache", {}))
        result = handle_filter_panel(
            adb=self.adb,
            page_detector=self.page_detector,
            icon_detector=self._icon_detector,
            page_info=page_info,
            rarity_codes=[rarity_code] if rarity_code else [],
            state=self._filter_state,
            action_cache=filter_action_cache,
        )
        if filter_action_cache.get("filter_selected") and filter_action_cache.get(
            "filter_ok_scrolled"
        ):
            self.mark_action_done("filter_applied")
        return result

    def _handle_exchange_target_confirm_page(self, page_info: dict) -> ActionResult:
        """确认页校验好友昵称和目标卡牌后点击确认。"""
        ocr = page_info.get("ocr_results", [])
        nickname = cast(Optional[str], self.state_get("friend_nickname"))
        set_code = cast(Optional[str], self.state_get("card_set_code"))
        number = cast(Optional[int], self.state_get("card_number"))

        if nickname and not is_text_visible(ocr, [nickname], exact=False):
            return self._fail("确认页目标昵称不匹配")

        if set_code and number is not None:
            detected = self._card_recognizer.scan(set_code=set_code)
            candidates = [
                item
                for item in detected
                if item.set_code == set_code and item.card_number == number
            ]
            if not candidates:
                logger.warning(
                    "确认页扫描未匹配: set_code=%s, number=%s", set_code, number
                )
                return self._fail("确认页卡牌不匹配")
            logger.info(
                "确认页扫描匹配: set_code=%s, number=%s, sim=%.2f",
                set_code,
                number,
                candidates[0].similarity,
            )

        return tap_ok(self.adb, ocr, wait=0.8) or ActionResult.wait(0.6)

    def _handle_exchange_proposed_done_popup(self, page_info: dict) -> ActionResult:
        request = self._req()
        if request is None:
            return ActionResult.wait(0.6)
        result = tap_ok(
            self.adb, page_info.get("ocr_results", []), wait=0.8
        ) or ActionResult.wait(0.6)
        if not result.success:
            return result

        with session_scope() as session:
            if not ExchangeCardRequestRepository(session).mark_sended(request.id, None):
                raise RuntimeError(f"交换请求标记 sended 失败: request_id={request.id}")
        request.expire_at = None
        request.cancel_reason = None
        request.failed_reason = None
        request.next_check_at = None
        request.status = "sended"
        self.state_set("request", request)
        logger.info("交换已送出，进入 5 分钟等待窗口")
        return ActionResult.ok(wait=1.0)

    def _handle_exchange_waiting_page(self, page_info: dict) -> ActionResult:
        request = self._req()
        if request is None:
            return ActionResult.wait(0.6)

        now = datetime.now()
        cancel_reason = request.cancel_reason
        recover = bool(self.state_get("recover"))
        cancel_mode = recover or bool(cancel_reason)

        if cancel_mode:
            if not self.is_action_done("waiting_cancel_clicked"):
                result = tap_text_exact(
                    self.adb,
                    page_info.get("ocr_results", []),
                    get_text_patterns("exchange_cancel_button"),
                    wait=0.8,
                )
                if result:
                    self.mark_action_done("waiting_cancel_clicked")
                    return result
            return ActionResult.wait(0.6)

        if not self.is_action_done("window_started"):
            request.expire_at = now + timedelta(seconds=EXCHANGE_WINDOW_SECONDS)
            request.updated_at = now
            self._update_request_fields(request.id, expire_at=request.expire_at)
            self.mark_action_done("window_started")
            logger.info("进入等待页，启动5分钟交换窗口: request_id=%s", request.id)

        if not cancel_reason and request.expire_at and now >= request.expire_at:
            request.cancel_reason = "等待对方回应超时（5分钟），自动取消"
            request.updated_at = now
            self._update_request_fields(request.id, cancel_reason=request.cancel_reason)
            logger.info("等待窗口超时: request_id=%s", request.id)

        if request.cancel_reason:
            return ActionResult.wait(0.6)

        result = tap_template(self.adb, self.page_detector, "btn_close", wait=0.8)
        return result or ActionResult.wait(1.0)

    def _handle_exchange_receive_confirm_page(self, page_info: dict) -> ActionResult:
        request = self._req()
        if request is None:
            return ActionResult.wait(0.6)

        ocr = page_info.get("ocr_results", [])
        if request.cancel_reason:
            return tap_text_exact(
                self.adb, ocr, get_text_patterns("exchange_reject_button"), wait=0.8
            ) or ActionResult.wait(0.6)
        return tap_text_exact(
            self.adb, ocr, get_text_patterns("exchange_send_button"), wait=0.8
        ) or ActionResult.wait(0.6)

    def _handle_exchange_canceled_done_popup(self, page_info: dict) -> ActionResult:
        """取消完成弹窗按恢复或结束分支收敛任务。"""
        request = self._req()
        if request is None:
            return ActionResult.wait(0.6)

        result = tap_ok(
            self.adb, page_info.get("ocr_results", []), wait=0.8
        ) or ActionResult.wait(0.6)
        if not result.success:
            return result

        if self.state_get("recover"):
            if not self.is_action_done("recover_clicked"):
                request.cancel_reason = None
                request.expire_at = None
                request.next_check_at = None
                request.updated_at = datetime.now()
                self._update_request_fields(
                    request.id,
                    cancel_reason=None,
                    expire_at=None,
                    next_check_at=None,
                )
                self.state_set("request", request)
                self.mark_action_done("recover_clicked")
                logger.info("旧提议已取消，等待页面退出后继续重发")
            return ActionResult.ok(wait=1.0)

        reason = request.cancel_reason or "交换已取消"
        with session_scope() as session:
            request_repo = ExchangeCardRequestRepository(session)
            if "超时" in reason:
                if not request_repo.mark_failed(request.id, reason):
                    raise RuntimeError(
                        f"交换请求标记 failed 失败: request_id={request.id}"
                    )
            else:
                if not request_repo.mark_canceled(request.id, reason=reason):
                    raise RuntimeError(
                        f"交换请求标记 canceled 失败: request_id={request.id}"
                    )
        self._done("交换超时失败" if "超时" in reason else "交换已取消")
        return result

    def _handle_exchange_locked_popup(self, page_info: dict) -> ActionResult:
        """交换未解锁弹窗点击确认并跳过任务。"""
        result = tap_ok(
            self.adb, page_info.get("ocr_results", []), wait=0.8
        ) or ActionResult.wait(0.6)
        if result.success:
            self._done("交换功能未解锁（14天冷冻期未到）", skip=True)
        return result

    def _handle_exchange_swipe_page(self, page_info: dict) -> ActionResult:
        if self._req() is None:
            return ActionResult.wait(0.6)
        if self.is_action_done("swiped"):
            return ActionResult.ok(wait=0.5)

        result = swipe_card_register(self.adb, wait=1.0)
        if not result.success:
            return result

        self.mark_action_done("swiped")
        self._finalize_success()
        self._done("交换完成")
        return ActionResult.ok(wait=0.8)

    def _tap_ok_popup(self, page_info: dict) -> ActionResult:
        """通用确认弹窗点击 OK。"""
        return tap_ok(
            self.adb, page_info.get("ocr_results", []), wait=0.8
        ) or ActionResult.wait(0.6)

    _handle_exchange_confirm_send_popup = _tap_ok_popup
    _handle_exchange_confirm_last_popup = _tap_ok_popup
    _handle_exchange_cancel_confirm_popup = _tap_ok_popup
    _handle_exchange_receive_start_popup = _tap_ok_popup

    def _finalize_success(self):
        """交换成功后同步请求状态与发送方库存。"""
        request = self._req()
        if request is None or self.account.id is None:
            return

        with session_scope() as session:
            repos = RepositoryFactory(session)
            if not repos.exchange_card_requests().mark_completed(request.id):
                raise RuntimeError(
                    f"交换请求标记 completed 失败: request_id={request.id}"
                )
            row = repos.account_cards().get(self.account.id, request.target_card_id)
            if row:
                repos.account_cards().upsert(
                    account_id=self.account.id,
                    card_id=request.target_card_id,
                    count=max(int(row.count) - 1, 0),
                    yolo_conf=getattr(row, "yolo_conf", None),
                    hash_similarity=getattr(row, "hash_similarity", None),
                )
        request.status = "completed"
        request.next_check_at = None
        request.failed_reason = None
        request.cancel_reason = None
        request.expire_at = None

    def _fail(
        self, reason: str, preserve_last_completed_at: bool = False
    ) -> ActionResult:
        """标记请求失败并结束任务。"""
        request = self._req()
        if request:
            with session_scope() as session:
                if not ExchangeCardRequestRepository(session).mark_failed(
                    request.id, reason
                ):
                    raise RuntimeError(
                        f"交换请求标记 failed 失败: request_id={request.id}"
                    )
        if preserve_last_completed_at:
            self.mark_completed_without_timestamp(reason)
        self._done(reason)
        return ActionResult.ok(wait=0.3)

    def _tap_target_card(self, detected) -> Optional[ActionResult]:
        """通过扫描定位目标卡牌。"""
        set_code = cast(Optional[str], self.state_get("card_set_code"))
        number = cast(Optional[int], self.state_get("card_number"))
        if set_code is None or number is None:
            return None

        candidates = [
            item
            for item in detected
            if item.set_code == set_code and item.card_number == number
        ]
        if not candidates:
            return None

        best = max(candidates, key=lambda item: (item.similarity, item.confidence))
        return tap(self.adb, int(best.center[0]), int(best.center[1]), wait=0.8)
