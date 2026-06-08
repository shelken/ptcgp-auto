# -*- coding: utf-8 -*-
"""
管理好友关系任务。

统一通过“搜索入口”处理三类请求：
- add + sending: 发送好友请求
- add + sended: 接受好友请求
- delete + deleting: 删除好友
"""

import logging
from datetime import datetime, timedelta
from typing import TYPE_CHECKING, Optional

from ptcgp_auto_v2.core.stateful_task import StatefulTask
from ptcgp_auto_v2.core.task_base import ActionResult, ResetType, TaskRegistry
from ptcgp_auto_v2.db.engine import session_scope
from ptcgp_auto_v2.db.repositories.exchange_card_request_repository import (
    ExchangeCardRequestRepository,
)
from ptcgp_auto_v2.db.repositories.account_repository import AccountRepository
from ptcgp_auto_v2.db.repositories.friend_request_repository import (
    FriendRequestRepository,
    FriendRequestSnapshot,
)
from ptcgp_auto_v2.db.repositories import FriendshipRepository
from ptcgp_auto_v2.locales import get_text_patterns
from ptcgp_auto_v2.tasks.utils.nickname_utils import extract_nickname_by_lv
from ptcgp_auto_v2.utils.gesture import (
    clear_text,
    find_text_matches,
    input_text,
    is_text_visible,
    tap_community_icon,
    tap_ok,
    tap_template_or_fallback,
    tap_template_with_scale,
    tap_text_exact,
)

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from ptcgp_auto_v2.core.hooks import Hook


def _build_manage_friendship_pages() -> list[dict]:
    """构建好友任务页面规则。"""
    return [
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
            "priority": 40,
        },
        # 朋友數 / 朋友 / 申請中 / 需回覆
        {
            "name": "friend_list",
            "identifiers": get_text_patterns("friend_page_list"),
            "match_all": True,
            "priority": 90,
        },
        # 新增朋友 modal：先显示自己的 ID/条码，需要再点朋友ID搜尋进入输入弹窗。
        {
            "name": "friend_add_modal",
            "identifiers": get_text_patterns("friend_add_modal"),
            "match_all": True,
            "priority": 89,
        },
        # 朋友ID搜尋 / OK
        {
            "name": "friend_search_popup",
            "identifiers": get_text_patterns("friend_search_popup"),
            "match_all": True,
            "priority": 88,
        },
        # 搜尋結果
        {
            "name": "friend_search_result_popup",
            "identifiers": get_text_patterns("friend_search_result_popup"),
            "priority": 91,
        },
        # 要移除朋友嗎？
        {
            "name": "friend_remove_confirm",
            "identifiers": get_text_patterns("friend_remove_confirm_title"),
            "priority": 95,
        },
    ]


# ============================================================
# 常量定义
# ============================================================

MAX_WAIT_ROUNDS_ADD_APPLY = 6
MAX_WAIT_ROUNDS_ACCEPT = 6
MAX_WAIT_ROUNDS_CANCEL_CLICK = 12
MAX_WAIT_ROUNDS_CANCEL_RESULT = 10
MAX_WAIT_ROUNDS_DELETE = 6


@TaskRegistry.register("manage_friendship")
class ManageFriendshipTask(StatefulTask):
    """好友请求统一处理任务。"""

    task_type = "manage_friendship"
    reset_type = ResetType.ONCE
    pages = _build_manage_friendship_pages()
    max_same_page_rounds = 20

    def __init__(self, adb, recognizer, page_detector):
        """初始化任务状态。"""
        super().__init__(adb, recognizer, page_detector)
        self.current_request: Optional[FriendRequestSnapshot] = None
        self.requests_to_process: list[FriendRequestSnapshot] = []
        self._active_request_id: Optional[int] = None
        self._submitted_request_id: Optional[int] = None
        self._returning_to_friend_list = False
        self._wake_account_ids: set[int] = set()
        self._reset_wait_rounds()

    def on_start(self):
        """任务开始前加载请求。"""
        self.state.reset()
        self.reset_action_cache()
        self.state_set("page.current", None)
        self._active_request_id = None
        self._submitted_request_id = None
        self._returning_to_friend_list = False
        self._reset_wait_rounds()
        self._wake_account_ids = set()

        self.requests_to_process = self._get_pending_requests()
        if self._expire_stale_add_requests():
            self.requests_to_process = self._get_pending_requests()
        self._log_pending_request_order("start")
        sending_count = sum(
            1
            for item in self.requests_to_process
            if item.request_type == "add" and item.status == "sending"
        )
        sended_count = sum(
            1
            for item in self.requests_to_process
            if item.request_type == "add" and item.status == "sended"
        )
        deleting_count = sum(
            1
            for item in self.requests_to_process
            if item.request_type == "delete" and item.status == "deleting"
        )
        logger.info(
            "manage_friendship 待处理请求: sending=%s, sended=%s, deleting=%s",
            sending_count,
            sended_count,
            deleting_count,
        )
        if not self.requests_to_process:
            self.mark_completed_without_timestamp("没有待处理的好友请求")
            self.complete()
            logger.info("没有待处理的好友请求，任务完成")

    def _reset_wait_rounds(self):
        """重置所有跨页等待计数。"""
        self._add_apply_wait_rounds = 0
        self._cancel_wait_rounds = 0
        self._accept_wait_rounds = 0
        self._delete_wait_rounds = 0

    def _expire_stale_add_requests(self) -> bool:
        """启动时清理已过期的 add 请求，避免长期卡住。"""
        changed = False
        now = datetime.now()
        for req in self.requests_to_process:
            if not self._is_add_request_expired(req, now):
                continue

            expire_minutes = self._get_add_request_expire_minutes(req.to_account_id)
            reason = f"好友请求超时未处理（{expire_minutes}分钟）"
            with session_scope() as session:
                repo = FriendRequestRepository(session)
                if not repo.update_status(req.id, "failed", failed_reason=reason):
                    raise RuntimeError(f"好友请求过期更新失败: request_id={req.id}")

            req.status = "failed"
            req.failed_reason = reason
            req.updated_at = now
            logger.info("好友请求已过期并标记失败: id=%s", req.id)
            changed = True
        return changed

    @staticmethod
    def _get_add_request_expire_minutes(to_account_id: Optional[int]) -> int:
        """按目标类型返回 add 请求过期分钟数。"""
        if to_account_id is None:
            return 10
        return 30

    @classmethod
    def _is_add_request_expired(
        cls, request: FriendRequestSnapshot, now: Optional[datetime] = None
    ) -> bool:
        """判断 add 请求是否已过期。"""
        if request.request_type != "add" or request.status not in {"sending", "sended"}:
            return False
        current = now or datetime.now()
        expire_minutes = cls._get_add_request_expire_minutes(request.to_account_id)
        return request.created_at <= current - timedelta(minutes=expire_minutes)

    def get_post_hooks(self) -> list["Hook"]:
        """任务结束后统一唤醒被影响账号的 manage_friendship。"""
        from ptcgp_auto_v2.hooks import ManageFriendshipWakePostHook

        return [ManageFriendshipWakePostHook()]

    def on_page_changed(
        self,
        previous_page_name: str | None,
        page_name: str,
        page_info: dict,
    ):
        """页面切换时重置页面动作缓存。"""
        self.reset_action_cache()

    def handle_unmapped_page(self, page_name: str, page_info: dict) -> ActionResult:
        return ActionResult.wait(0.8)

    def _get_pending_requests(self) -> list[FriendRequestSnapshot]:
        """读取当前账号待处理请求，并严格按创建时间升序排序。"""
        if self.account.id is None:
            return []
        with session_scope() as session:
            repo = FriendRequestRepository(session)
            pending_requests = repo.list_manage_friendship_pending_data(self.account.id)
        pending_requests.sort(key=self._request_order_key)
        return pending_requests

    @staticmethod
    def _request_order_key(req: FriendRequestSnapshot) -> tuple[datetime, int]:
        """请求排序键：先按创建时间，再按ID，保证旧请求优先执行。"""
        return req.created_at, req.id

    def _refresh_requests(self):
        """刷新请求列表。"""
        self.requests_to_process = self._get_pending_requests()
        self._log_pending_request_order("refresh")
        self.current_request = None
        self._active_request_id = None
        self._submitted_request_id = None
        if not self.requests_to_process:
            self._returning_to_friend_list = True

    def _defer_current_request(self, req: FriendRequestSnapshot, stage: str):
        """本轮暂缓当前请求，避免同一轮重复查询同一请求。"""
        self.requests_to_process = [
            item for item in self.requests_to_process if item.id != req.id
        ]
        self.current_request = None
        self._active_request_id = None
        self._submitted_request_id = None
        self.reset_action_cache()
        self._reset_wait_rounds()
        self._log_pending_request_order(stage)
        if not self.requests_to_process:
            self._returning_to_friend_list = True

    def _log_pending_request_order(self, stage: str):
        """输出当前待处理请求顺序，便于排查是否按创建时间执行。"""
        if not self.requests_to_process:
            logger.debug("[%s] 当前无待处理好友请求", stage)
            return

        order_text = " | ".join(
            (
                f"id={item.id},type={item.request_type},status={item.status},"
                f"created_at={item.created_at}"
            )
            for item in self.requests_to_process
        )
        logger.debug("[%s] 好友请求处理顺序(旧->新): %s", stage, order_text)

    def _pick_current_request(self) -> Optional[FriendRequestSnapshot]:
        """获取当前处理请求。"""
        if self.current_request is None and self.requests_to_process:
            self.current_request = self.requests_to_process[0]
            logger.info(
                "当前处理请求: id=%s type=%s status=%s from=%s to_account=%s to_friend=%s",
                self.current_request.id,
                self.current_request.request_type,
                self.current_request.status,
                self.current_request.from_account_id,
                self.current_request.to_account_id,
                self.current_request.to_friend_id,
            )
        return self.current_request

    def _save_request(
        self, req: FriendRequestSnapshot, status: str, failed_reason: Optional[str] = None
    ):
        """持久化请求状态。"""
        with session_scope() as session:
            repo = FriendRequestRepository(session)
            if not repo.update_status(req.id, status, failed_reason=failed_reason):
                raise RuntimeError(f"好友请求状态更新失败: request_id={req.id}")
        req.status = status
        req.failed_reason = failed_reason
        req.updated_at = datetime.now()

    def _close_modal(self, wait: float = 0.8) -> ActionResult:
        """点击关闭按钮。"""
        return tap_template_or_fallback(
            self.adb,
            self.page_detector,
            "btn_close",
            fallback_action=lambda: ActionResult.wait(wait),
            wait=wait,
        )

    def _resolve_request_friend_id(self, req: FriendRequestSnapshot) -> Optional[str]:
        """解析请求目标 friend_id。"""
        if (
            req.request_type == "add"
            and req.status == "sended"
            and req.to_account_id == self.account.id
        ):
            with session_scope() as session:
                sender = AccountRepository(session).get_friend_ref_by_id(
                    req.from_account_id
                )
            if sender and sender.friend_id:
                return sender.friend_id

        if req.to_friend_id:
            return req.to_friend_id

        if req.to_account_id:
            with session_scope() as session:
                target = AccountRepository(session).get_friend_ref_by_id(
                    req.to_account_id
                )
            if target and target.friend_id:
                return target.friend_id
        return None

    def _extract_nickname_from_ocr(
        self,
        ocr_results: list[dict],
    ) -> Optional[str]:
        """从搜索结果 OCR 中提取目标昵称（Lv 下方）。"""
        return extract_nickname_by_lv(
            ocr_results=ocr_results,
            search_range_y=self.adb.scaled_y(300),
            excluded_contains=get_text_patterns("profile_exclude"),
        )

    def _save_target_nickname(
        self, req: FriendRequestSnapshot, ocr_results: list[dict]
    ):
        """保存好友请求与交换请求的目标昵称。"""
        if req.request_type != "add" or req.status != "sending":
            return
        target_friend_id = self._resolve_request_friend_id(req)
        nickname = self._extract_nickname_from_ocr(ocr_results)
        if not nickname:
            return
        if req.to_nickname == nickname:
            return

        with session_scope() as session:
            repo = FriendRequestRepository(session)
            if not repo.update_nickname(req.id, nickname):
                raise RuntimeError(f"好友请求昵称更新失败: request_id={req.id}")
        req.to_nickname = nickname
        req.updated_at = datetime.now()

        if target_friend_id and self.account.id is not None:
            with session_scope() as session:
                repo = ExchangeCardRequestRepository(session)
                repo.update_active_nickname(
                    from_account_id=self.account.id,
                    to_friend_id=target_friend_id,
                    to_nickname=nickname,
                )

    def _is_pending_reply_by_icons(self) -> bool:
        """1.0 模板下同时有绿色勾和红色叉，判定为待回复状态。"""
        green_1x = self.page_detector.find_template_with_scale(
            "icon_green_yes", scale=1.0, threshold=0.8
        )
        red_1x = self.page_detector.find_template_with_scale(
            "icon_red_no", scale=1.0, threshold=0.8
        )
        return green_1x is not None and red_1x is not None

    def _is_already_friend_by_icons(self) -> bool:
        """0.8 模板下命中绿色勾，判定为已是好友状态。"""
        green_08 = self.page_detector.find_template_with_scale(
            "icon_green_yes", scale=0.8, threshold=0.8
        )
        return green_08 is not None

    def _is_friend_confirmed_by_icons(self, request_id: Optional[int] = None) -> bool:
        """仅当存在绿色勾且不存在红叉时，判定为已确认好友。"""
        green_match = self.page_detector.find_template_with_scale(
            "icon_green_yes", scale=1.0, threshold=0.8
        )
        if not green_match:
            green_match = self.page_detector.find_template_with_scale(
                "icon_green_yes", scale=0.8, threshold=0.8
            )
        red_match = self.page_detector.find_template_with_scale(
            "icon_red_no", scale=1.0, threshold=0.8
        )
        if not red_match:
            red_match = self.page_detector.find_template_with_scale(
                "icon_red_no", scale=0.8, threshold=0.8
            )

        if green_match and not red_match:
            return True

        if green_match and red_match:
            if request_id is not None:
                logger.debug(
                    "请求 %s 同时检测到绿色勾和红叉，判定为待处理状态",
                    request_id,
                )
            else:
                logger.debug("同时检测到绿色勾和红叉，判定为待处理状态")
        return False

    def _tap_green_yes(self, wait: float = 0.8) -> Optional[ActionResult]:
        """点击绿色勾模板（优先 1.0，其次 0.8）。"""
        result = tap_template_with_scale(
            self.page_detector,
            "icon_green_yes",
            scale=1.0,
            threshold=0.8,
            wait=wait,
        )
        if result:
            return result
        return tap_template_with_scale(
            self.page_detector,
            "icon_green_yes",
            scale=0.8,
            threshold=0.8,
            wait=wait,
        )

    def _handle_friend_list(self, page_info: dict) -> ActionResult:
        """好友列表页统一进入搜索入口。"""
        if self.is_completed():
            return ActionResult.ok(wait=0.5)
        if self._returning_to_friend_list:
            self._returning_to_friend_list = False
            self.complete()
            return ActionResult.ok(wait=0.5)
        req = self._pick_current_request()
        if req is None:
            self.complete()
            return ActionResult.ok(wait=0.5)
        return tap_template_or_fallback(
            self.adb,
            self.page_detector,
            "icon_add_friends",
            fallback_action=lambda: ActionResult.wait(0.8),
            wait=0.9,
        )

    def _handle_home_with_community_icon(self, page_info: dict) -> ActionResult:
        """主页社群图标：进入社群。"""
        if self.is_completed():
            return ActionResult.ok(wait=0.5)
        return tap_community_icon(self.adb, self.page_detector)

    def _handle_game_home_main(self, page_info: dict) -> ActionResult:
        """主页文本：进入社群。"""
        if self.is_completed():
            return ActionResult.ok(wait=0.5)
        return tap_community_icon(self.adb, self.page_detector)

    def _handle_community_page(self, page_info: dict) -> ActionResult:
        """社群页：进入朋友页。"""
        result = tap_text_exact(
            self.adb,
            page_info.get("ocr_results", []),
            get_text_patterns("friend_tab_friends"),
            wait=1.0,
        )
        return result or ActionResult.wait(0.8)

    def _handle_friend_add_modal(self, page_info: dict) -> ActionResult:
        """新增朋友 modal：进入朋友ID搜索输入弹窗。"""
        if self._returning_to_friend_list:
            logger.debug("关闭新增朋友 modal，回到好友列表")
            return self._close_modal(wait=0.8)

        result = tap_text_exact(
            self.adb,
            page_info.get("ocr_results", []),
            get_text_patterns("friend_id_search"),
            wait=0.8,
        )
        return result or ActionResult.wait(0.5)

    def _handle_friend_search_popup(self, page_info: dict) -> ActionResult:
        """朋友ID搜索弹窗：每个请求强制执行 清空->输入->搜索。"""
        ocr_results = page_info.get("ocr_results", [])
        if self._returning_to_friend_list:
            logger.debug("关闭朋友ID搜索弹窗，回到好友列表")
            result = tap_text_exact(
                self.adb,
                ocr_results,
                get_text_patterns("text_cancel"),
                wait=0.8,
            )
            return result or self._close_modal(wait=0.8)

        req = self._pick_current_request()
        if req is None:
            self._returning_to_friend_list = True
            return ActionResult.wait(0.5)

        target_friend_id = self._resolve_request_friend_id(req)
        if not target_friend_id:
            self._save_request(req, "failed", failed_reason="缺少目标 friend_id")
            self._refresh_requests()
            return ActionResult.wait(0.5)

        request_id = req.id
        if request_id != self._active_request_id:
            self._active_request_id = request_id
            self._submitted_request_id = None
            self.reset_action_cache()
            self._reset_wait_rounds()

        input_matches = find_text_matches(
            ocr_results,
            get_text_patterns("friend_id_input_placeholder"),
            exact=True,
        )
        if input_matches:
            input_box = input_matches[0]["box"]
            focus_point = self.adb.center_x(), (input_box[1] + input_box[3]) // 2

            if not self.is_action_done("search_cleared"):
                logger.debug("请求 %s: 点击并清空朋友ID输入框", request_id)
                clear_text(
                    self.adb, focus_point[0], focus_point[1], max_chars=24, wait=0.2
                )
                self.mark_action_done("search_cleared")
                return ActionResult.wait(0.4)

            if not self.is_action_done("search_input_done"):
                logger.debug(
                    "请求 %s: 输入目标friend_id=%s", request_id, target_friend_id
                )
                input_text(self.adb, target_friend_id, wait=0.3)
                self.mark_action_done("search_input_done")
                return ActionResult.wait(0.6)

            return ActionResult.wait(0.6)

        if not self.is_action_done("search_input_done"):
            logger.debug("输入框已填但不是当前流程输入，关闭输入弹窗回到列表")
            self._returning_to_friend_list = True
            result = tap_text_exact(
                self.adb,
                ocr_results,
                get_text_patterns("text_cancel"),
                wait=0.8,
            )
            return result or self._close_modal(wait=0.8)

        if not self.is_action_done("search_submitted"):
            result = tap_ok(self.adb, ocr_results, wait=0.9)
            if result:
                self.mark_action_done("search_submitted")
                self._submitted_request_id = request_id
                return result
            return ActionResult.wait(0.8)

        return ActionResult.wait(0.6)

    def _handle_friend_search_result_popup(self, page_info: dict) -> ActionResult:
        """搜索结果弹窗统一处理三类请求。"""
        if self._returning_to_friend_list:
            logger.debug("关闭搜索结果弹窗，回到好友列表")
            return self._close_modal(wait=0.8)

        req = self._pick_current_request()
        if req is None:
            self._returning_to_friend_list = True
            return self._close_modal(wait=0.8)

        # 关键约束：切换请求后，不复用旧搜索结果，先关闭结果页回到搜索输入页重搜
        if req.id != self._active_request_id:
            self._active_request_id = req.id
            self._submitted_request_id = None
            self.reset_action_cache()
            self._reset_wait_rounds()
            logger.debug("请求已切换，关闭当前搜索结果，回到搜索页重查目标friend_id")
            return self._close_modal(wait=0.8)

        # 严格约束：只有当前请求主动点过搜索按钮后，才能消费搜索结果。
        # 否则该结果视为“上一请求残留结果”，必须先关闭回到搜索页。
        if self._submitted_request_id != req.id:
            logger.debug("检测到残留搜索结果，关闭搜索结果和输入弹窗后回到列表")
            self._active_request_id = None
            self._submitted_request_id = None
            self._returning_to_friend_list = True
            self.reset_action_cache()
            return self._close_modal(wait=0.8)

        if req.request_type == "add" and req.status == "sending":
            return self._handle_add_sending_result(req, page_info)
        if req.request_type == "add" and req.status == "sended":
            return self._handle_add_sended_result(req, page_info)
        if req.request_type == "add" and req.status == "canceling":
            return self._handle_add_canceling_result(req, page_info)
        if req.request_type == "delete" and req.status == "deleting":
            return self._handle_delete_result(req, page_info)
        return ActionResult.wait(0.6)

    def _handle_add_sending_result(self, req, page_info: dict) -> ActionResult:
        """处理发送好友请求结果。"""
        ocr_results = page_info.get("ocr_results", [])

        if is_text_visible(
            ocr_results, get_text_patterns("friend_cancel_request"), exact=True
        ):
            self._save_target_nickname(req, ocr_results)
            self._save_request(req, "sended")
            if req.to_account_id:
                self._wake_account_ids.add(req.to_account_id)
            # 发送成功后本轮不再立刻重查同一请求，避免连续两次搜索同一 friend_id。
            # 外部好友保持 sended，等待后续任务再次确认是否已接受。
            self._defer_current_request(req, "defer_add_sent")
            return self._close_modal(wait=0.8)

        if self._is_pending_reply_by_icons():
            logger.warning(
                "请求 %s 检测到待回复状态（1.0命中红叉+绿勾），当前先不自动处理",
                req.id,
            )
            self._defer_current_request(req, "defer_sending_pending_reply")
            return self._close_modal(wait=0.8)

        if self._is_already_friend_by_icons():
            logger.info("请求 %s 检测到已是好友状态（0.8绿色勾）", req.id)
            self._complete_add_already_friend_request(req)
            self._refresh_requests()
            return self._close_modal(wait=0.8)

        apply_result = tap_text_exact(
            self.adb,
            ocr_results,
            get_text_patterns("friend_apply_button"),
            wait=0.9,
        )
        if apply_result:
            logger.info("请求 %s 检测到申请按钮，执行申请点击", req.id)
            self.mark_action_done("add_apply_clicked")
            self._add_apply_wait_rounds = 0
            return apply_result

        if not self.is_action_done("add_apply_clicked"):
            # 尚未进入发送态，且当前未识别到申请按钮，继续等待刷新。
            return ActionResult.wait(0.6)

        self._add_apply_wait_rounds += 1
        if self._add_apply_wait_rounds >= MAX_WAIT_ROUNDS_ADD_APPLY:
            self._save_request(req, "failed", failed_reason="发送后未出现取消交友邀请")
            self._refresh_requests()
            return self._close_modal(wait=0.8)
        return ActionResult.wait(0.8)

    def _complete_add_already_friend_request(self, req):
        """处理发送侧检测到已是好友的完成逻辑，并补齐关系表。"""
        current_account_id = self.account.id
        if current_account_id is None:
            self._save_request(req, "failed", failed_reason="当前账号ID为空")
            return

        # 请求完成
        self._save_request(req, "completed")

        # 优先补齐当前账号 -> 目标账号的关系
        if req.to_friend_id:
            with session_scope() as session:
                repo = FriendshipRepository(session)
                repo.create(current_account_id, req.to_friend_id, req.to_account_id)

        # 若有目标账号信息，尝试补齐双向关系
        if req.to_account_id:
            with session_scope() as session:
                target = AccountRepository(session).get_friend_ref_by_id(
                    req.to_account_id
                )
            if target and target.friend_id:
                with session_scope() as session:
                    repo = FriendshipRepository(session)
                    repo.create(current_account_id, target.friend_id, target.id)
            if target and target.id and self.account.friend_id:
                with session_scope() as session:
                    repo = FriendshipRepository(session)
                    repo.create(
                        target.id,
                        self.account.friend_id,
                        current_account_id,
                    )

    def _handle_add_sended_result(self, req, page_info: dict) -> ActionResult:
        """处理接受好友请求结果（系统内）或确认外部好友是否已接受。"""
        # 外部好友：to_account_id 为 null，检查是否已是好友
        if req.to_account_id is None:
            return self._handle_external_sended_result(req, page_info)

        # 系统内好友：接受对方发来的请求
        if not self.is_action_done("accept_green_clicked"):
            green_click_result = self._tap_green_yes(wait=0.8)
            if green_click_result:
                self.mark_action_done("accept_green_clicked")
                return green_click_result

        if self.is_action_done("accept_green_clicked"):
            close_result = self._close_modal(wait=0.8)
            if close_result.success:
                self._complete_add_sended_request(req)
            return close_result

        self._accept_wait_rounds += 1
        if self._accept_wait_rounds >= MAX_WAIT_ROUNDS_ACCEPT:
            self._save_request(req, "failed", failed_reason="接受流程未找到绿色勾")
            self._refresh_requests()
            return self._close_modal(wait=0.8)
        return ActionResult.wait(0.8)

    def _handle_external_sended_result(self, req, page_info: dict) -> ActionResult:
        """处理外部好友 sended 状态：检查是否已是好友。"""
        ocr_results = page_info.get("ocr_results", [])

        # 看到绿色勾：对方已接受，成为好友
        if self._is_friend_confirmed_by_icons(req.id):
            logger.info("外部好友请求 %s 仅检测到绿色勾，对方已接受", req.id)
            self._save_request(req, "completed")
            if req.to_friend_id and self.account.id is not None:
                with session_scope() as session:
                    repo = FriendshipRepository(session)
                    repo.create(self.account.id, req.to_friend_id, req.to_account_id)
            self._refresh_requests()
            return self._close_modal(wait=0.8)

        # 看到取消交友邀请：对方还没接受，保持 sended
        if is_text_visible(
            ocr_results, get_text_patterns("friend_cancel_request"), exact=True
        ):
            logger.debug("外部好友请求 %s 对方尚未接受，保持 sended", req.id)
            self._defer_current_request(req, "defer_external_pending")
            return self._close_modal(wait=0.8)

        self._accept_wait_rounds += 1
        if self._accept_wait_rounds >= MAX_WAIT_ROUNDS_ACCEPT:
            logger.debug("外部好友请求 %s 状态不明确，保持 sended", req.id)
            self._defer_current_request(req, "defer_external_unclear")
            return self._close_modal(wait=0.8)
        return ActionResult.wait(0.8)

    def _handle_add_canceling_result(self, req, page_info: dict) -> ActionResult:
        """处理取消已发送邀请结果。"""
        ocr_results = page_info.get("ocr_results", [])

        # 出现申请按钮代表取消成功
        if is_text_visible(
            ocr_results, get_text_patterns("friend_apply_button"), exact=True
        ):
            self._save_request(req, "failed", failed_reason="已取消交友邀请")
            self._refresh_requests()
            return self._close_modal(wait=0.8)

        cancel_visible = is_text_visible(
            ocr_results,
            get_text_patterns("friend_cancel_request"),
            exact=True,
        )

        # 按用户要求：只要看到取消交友邀请就立刻点击
        cancel_result = tap_text_exact(
            self.adb,
            ocr_results,
            get_text_patterns("friend_cancel_request"),
            wait=0.8,
        )
        if cancel_result:
            logger.info("取消邀请流程: 检测到取消交友邀请，立即点击")
            self._cancel_wait_rounds += 1
            return cancel_result

        if cancel_visible:
            self._cancel_wait_rounds += 1
            if self._cancel_wait_rounds >= MAX_WAIT_ROUNDS_CANCEL_CLICK:
                self._save_request(
                    req, "failed", failed_reason="取消邀请按钮可见但点击失败"
                )
                self._refresh_requests()
                return self._close_modal(wait=0.8)
            return ActionResult.wait(0.6)

        # 看不到取消按钮也没看到申请按钮，先等待一轮再判定
        self._cancel_wait_rounds += 1
        if self._cancel_wait_rounds >= MAX_WAIT_ROUNDS_CANCEL_RESULT:
            self._save_request(req, "failed", failed_reason="取消邀请结果页状态不明确")
            self._refresh_requests()
            return self._close_modal(wait=0.8)
        return ActionResult.wait(0.8)

    def _handle_delete_result(self, req, page_info: dict) -> ActionResult:
        """处理删除好友结果。"""
        ocr_results = page_info.get("ocr_results", [])

        # 删除判定：看到申请按钮说明已非好友，直接完成
        if is_text_visible(
            ocr_results, get_text_patterns("friend_apply_button"), exact=True
        ):
            self._save_request(req, "completed")
            self._refresh_requests()
            return self._close_modal(wait=0.8)

        if not self.is_action_done("delete_green_clicked"):
            green_click_result = self._tap_green_yes(wait=0.8)
            if green_click_result:
                self.mark_action_done("delete_green_clicked")
                return green_click_result

        if self.is_action_done("delete_green_clicked"):
            return ActionResult.wait(0.6)

        self._delete_wait_rounds += 1
        if self._delete_wait_rounds >= MAX_WAIT_ROUNDS_DELETE:
            self._save_request(
                req, "failed", failed_reason="删除结果页未出现绿色勾或申请"
            )
            self._refresh_requests()
            return self._close_modal(wait=0.8)
        return ActionResult.wait(0.8)

    def _handle_friend_remove_confirm(self, page_info: dict) -> ActionResult:
        """删除确认弹窗点击 OK。"""
        req = self._pick_current_request()
        if req is None:
            return ActionResult.wait(0.5)
        result = tap_ok(self.adb, page_info.get("ocr_results", []), wait=0.8)
        if result:
            return result
        return ActionResult.wait(0.6)

    def _complete_add_sended_request(self, req):
        """接受完成后更新状态并建立双向关系。"""
        current_account_id = self.account.id
        if current_account_id is None:
            self._save_request(req, "failed", failed_reason="当前账号ID为空")
            self._refresh_requests()
            return

        with session_scope() as session:
            sender = AccountRepository(session).get_friend_ref_by_id(
                req.from_account_id
            )
        if sender is None or sender.id is None or not sender.friend_id:
            self._save_request(req, "failed", failed_reason="发送方账号信息不完整")
            self._refresh_requests()
            return

        self._save_request(req, "completed")
        with session_scope() as session:
            repo = FriendshipRepository(session)
            repo.create(current_account_id, sender.friend_id, sender.id)
        if self.account.friend_id:
            with session_scope() as session:
                repo = FriendshipRepository(session)
                repo.create(sender.id, self.account.friend_id, current_account_id)
        self._refresh_requests()
