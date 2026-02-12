# -*- coding: utf-8 -*-
"""
交换卡牌任务。

基于 ExchangeCardRequest 请求状态机推进 sending/sended 两阶段。
"""

from datetime import datetime, timedelta
from typing import Optional

from ptcgp_auto_v2.core.task_base import ActionResult, ResetType, Task, TaskRegistry
from ptcgp_auto_v2.db.models import ExchangeCardRequest
from ptcgp_auto_v2.db.repositories import ExchangeCardRequestRepository
from ptcgp_auto_v2.locales import get_text_patterns
from ptcgp_auto_v2.utils.gesture import tap_text_exact


def _build_exchange_cards_pages() -> list[dict]:
    """构建交换卡牌任务页面规则。"""
    return [
        {
            "name": "exchange_target_page",
            "identifiers": get_text_patterns("exchange_target_page"),
            "priority": 80,
        },
        {
            "name": "exchange_record_page",
            "identifiers": get_text_patterns("exchange_record_page"),
            "priority": 81,
        },
    ]


@TaskRegistry.register("exchange_cards")
class ExchangeCardsTask(Task):
    """交换卡牌任务：处理 sending/sended 请求。"""

    task_type = "exchange_cards"
    reset_type = ResetType.ONCE
    pages = _build_exchange_cards_pages()
    max_unknown_pages = 20

    def __init__(self, adb, recognizer, page_detector):
        super().__init__(adb, recognizer, page_detector)
        self._request_repo = ExchangeCardRequestRepository()
        self._current_request: Optional[ExchangeCardRequest] = None
        self._completed = False
        self._complete_reason: Optional[str] = None

    def on_start(self):
        """加载当前账号活跃交换请求。"""
        self._completed = False
        self._complete_reason = None
        self._current_request = None

        if self.account.id is None:
            self._completed = True
            self._complete_reason = "账号ID为空"
            return

        active_request = self._request_repo.get_active_by_account(self.account.id)
        if active_request is None:
            self._completed = True
            self._complete_reason = "无活跃交换请求"
            return
        self._current_request = active_request

    def is_completed(self) -> bool:
        """任务是否完成。"""
        return self._completed

    def handle_page(self, page_name: str, page_info: dict) -> ActionResult:
        """按页面分发请求处理。"""
        if self._current_request is None:
            self._completed = True
            return ActionResult.ok(wait=0.2)

        if (
            self._current_request.status == "sending"
            and page_name == "exchange_target_page"
        ):
            return self._handle_exchange_target_page(page_info)

        if (
            self._current_request.status == "sended"
            and page_name == "exchange_record_page"
        ):
            return self._handle_exchange_record_page(page_info)

        return ActionResult.wait(0.6)

    def _handle_exchange_target_page(self, page_info: dict) -> ActionResult:
        """sending 阶段：点击送出按钮并推进到 sended。"""
        if self._current_request is None:
            self._completed = True
            return ActionResult.ok(wait=0.2)

        ocr_results = page_info.get("ocr_results", [])
        send_result = tap_text_exact(
            self.adb,
            ocr_results,
            get_text_patterns("exchange_send_button"),
            wait=0.8,
            exact=True,
        )
        if not send_result:
            return ActionResult.wait(0.6)

        self._current_request.status = "sended"
        self._current_request.next_check_at = datetime.now() + timedelta(minutes=5)
        self._current_request.updated_at = datetime.now()
        self._request_repo.update(self._current_request)
        self._completed = True
        self._complete_reason = "交换请求已送出，等待复查"
        return send_result

    def _handle_exchange_record_page(self, page_info: dict) -> ActionResult:
        """sended 阶段：到达记录页后延后复查并收敛本轮任务。"""
        if self._current_request is None:
            self._completed = True
            return ActionResult.ok(wait=0.2)

        self._current_request.next_check_at = datetime.now() + timedelta(minutes=5)
        self._current_request.updated_at = datetime.now()
        self._request_repo.update(self._current_request)
        self._completed = True
        self._complete_reason = "交换请求待对方处理，延后复查"
        return ActionResult.ok(wait=0.4)
