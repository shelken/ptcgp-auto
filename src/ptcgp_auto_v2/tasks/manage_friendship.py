# -*- coding: utf-8 -*-
"""
管理好友关系任务。

统一通过“搜索入口”处理三类请求：
- add + sending: 发送好友请求
- add + sended: 接受好友请求
- delete + deleting: 删除好友
"""

import logging
from datetime import datetime
from typing import TYPE_CHECKING, Optional

from ptcgp_auto_v2.core.task_base import ActionResult, ResetType, Task, TaskRegistry
from ptcgp_auto_v2.db.repositories import (
    AccountRepository,
    ExchangeCardRequestRepository,
    FriendRequestRepository,
    FriendshipRepository,
)
from ptcgp_auto_v2.locales import get_text_patterns
from ptcgp_auto_v2.services import FriendshipService
from ptcgp_auto_v2.tasks.utils.nickname_utils import extract_nickname_by_lv
from ptcgp_auto_v2.utils.gesture import (
    clear_text,
    input_text,
    is_text_visible,
    tap_community_icon,
    tap_ok,
    tap_template,
    tap_template_or_fallback,
    tap_template_with_scale,
    tap_text_exact,
)

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from ptcgp_auto_v2.core.hooks import Hook
    from ptcgp_auto_v2.db.models import AccountFriendRequest


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
        # 搜索图标
        {
            "name": "friend_search_modal",
            "templates": ["icon_search"],
            "priority": 90,
        },
        # 搜尋結果
        {
            "name": "friend_search_result_modal",
            "identifiers": get_text_patterns("friend_page_search_result"),
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
class ManageFriendshipTask(Task):
    """好友请求统一处理任务。"""

    task_type = "manage_friendship"
    reset_type = ResetType.ONCE
    pages = _build_manage_friendship_pages()
    max_same_page_rounds = 20

    def __init__(self, adb, recognizer, page_detector):
        """初始化任务状态。"""
        super().__init__(adb, recognizer, page_detector)
        self.current_request: Optional["AccountFriendRequest"] = None
        self.requests_to_process: list["AccountFriendRequest"] = []
        self._action_cache: dict[str, bool] = {}
        self._last_page_name: Optional[str] = None
        self._active_request_id: Optional[int] = None
        self._submitted_request_id: Optional[int] = None
        self._completed = False
        self._wake_account_ids: set[int] = set()

        self._add_apply_wait_rounds = 0
        self._cancel_wait_rounds = 0
        self._accept_wait_rounds = 0
        self._delete_wait_rounds = 0

    def _is_action_done(self, key: str) -> bool:
        """检查动作标记。"""
        return self._action_cache.get(key, False)

    def _mark_action_done(self, key: str):
        """记录动作标记。"""
        self._action_cache[key] = True

    def _reset_action_cache(self):
        """清空页面内动作标记。"""
        self._action_cache.clear()

    def on_start(self):
        """任务开始前加载请求。"""
        self._reset_action_cache()
        self._last_page_name = None
        self._active_request_id = None
        self._submitted_request_id = None
        self._add_apply_wait_rounds = 0
        self._cancel_wait_rounds = 0
        self._accept_wait_rounds = 0
        self._delete_wait_rounds = 0
        self._wake_account_ids = set()

        self.requests_to_process = self._get_pending_requests()
        if self._expire_stale_add_requests():
            self.requests_to_process = self._get_pending_requests()
        self._log_pending_request_order("start")
        logger.info(
            "manage_friendship 待处理请求: sending=%s, sended=%s, deleting=%s",
            len(
                [
                    item
                    for item in self.requests_to_process
                    if item.request_type == "add" and item.status == "sending"
                ]
            ),
            len(
                [
                    item
                    for item in self.requests_to_process
                    if item.request_type == "add" and item.status == "sended"
                ]
            ),
            len(
                [
                    item
                    for item in self.requests_to_process
                    if item.request_type == "delete" and item.status == "deleting"
                ]
            ),
        )
        if not self.requests_to_process:
            self.mark_completed_without_timestamp("没有待处理的好友请求")
            self._completed = True
            logger.info("没有待处理的好友请求，任务完成")

    def _expire_stale_add_requests(self) -> bool:
        """启动时清理已过期的 add 请求，避免长期卡住。"""
        changed = False
        now = datetime.now()
        for req in self.requests_to_process:
            if FriendshipService.expire_add_request_if_needed(req, now=now):
                logger.info("好友请求已过期并标记失败: id=%s", getattr(req, "id", None))
                changed = True
        return changed

    def is_completed(self) -> bool:
        """返回任务是否完成。"""
        return self._completed

    def get_post_hooks(self) -> list["Hook"]:
        """任务结束后统一唤醒被影响账号的 manage_friendship。"""
        from ptcgp_auto_v2.hooks import ManageFriendshipWakePostHook

        return [ManageFriendshipWakePostHook()]

    def handle_page(self, page_name: str, page_info: dict) -> ActionResult:
        """按页面分发处理。"""
        if page_name != self._last_page_name:
            self._reset_action_cache()
            self._last_page_name = page_name

        handlers = {
            "home_with_community_icon": self._handle_home,
            "game_home_main": self._handle_home,
            "community_page": self._handle_community,
            "friend_list": self._handle_friend_list,
            "friend_search_modal": self._handle_search_modal,
            "friend_search_result_modal": self._handle_search_result,
            "friend_remove_confirm": self._handle_remove_confirm,
        }
        handler = handlers.get(page_name)
        if handler:
            return handler(page_info)
        return ActionResult.wait(0.8)

    def _get_pending_requests(self) -> list["AccountFriendRequest"]:
        """读取当前账号待处理请求，并严格按创建时间升序排序。"""
        if self.account.id is None:
            return []
        repo = FriendRequestRepository()
        sending = repo.get_by_from_account_and_status(self.account.id, "sending")
        sended = repo.get_add_requests_by_to_account_and_status(
            self.account.id, "sended"
        )
        external_sended = repo.get_external_sended_requests(self.account.id)
        canceling = repo.get_by_from_account_and_type(
            self.account.id, "add", "canceling"
        )
        deleting = repo.get_by_from_account_and_type(
            self.account.id, "delete", "deleting"
        )
        pending_requests = (
            list(sending)
            + list(sended)
            + list(external_sended)
            + list(canceling)
            + list(deleting)
        )
        pending_requests.sort(key=self._request_order_key)
        return pending_requests

    @staticmethod
    def _request_order_key(req) -> tuple[datetime, int]:
        """请求排序键：先按创建时间，再按ID，保证旧请求优先执行。"""
        created_at = getattr(req, "created_at", None)
        request_id = getattr(req, "id", None)

        if not isinstance(created_at, datetime):
            created_at = datetime.max
        if not isinstance(request_id, int):
            request_id = 2**31 - 1

        return created_at, request_id

    def _refresh_requests(self):
        """刷新请求列表。"""
        self.requests_to_process = self._get_pending_requests()
        self._log_pending_request_order("refresh")
        self.current_request = None
        self._active_request_id = None
        self._submitted_request_id = None
        if not self.requests_to_process:
            self._completed = True

    def _defer_current_request(self, req, stage: str):
        """本轮暂缓当前请求，避免同一轮重复查询同一请求。"""
        req_id = getattr(req, "id", None)
        if req_id is not None:
            self.requests_to_process = [
                item
                for item in self.requests_to_process
                if getattr(item, "id", None) != req_id
            ]
        self.current_request = None
        self._active_request_id = None
        self._submitted_request_id = None
        self._reset_action_cache()
        self._add_apply_wait_rounds = 0
        self._cancel_wait_rounds = 0
        self._accept_wait_rounds = 0
        self._delete_wait_rounds = 0
        self._log_pending_request_order(stage)
        if not self.requests_to_process:
            self._completed = True

    def _log_pending_request_order(self, stage: str):
        """输出当前待处理请求顺序，便于排查是否按创建时间执行。"""
        if not self.requests_to_process:
            logger.debug("[%s] 当前无待处理好友请求", stage)
            return

        order_text = " | ".join(
            (
                f"id={item.id},type={item.request_type},status={item.status},"
                f"created_at={getattr(item, 'created_at', None)}"
            )
            for item in self.requests_to_process
        )
        logger.debug("[%s] 好友请求处理顺序(旧->新): %s", stage, order_text)

    def _pick_current_request(self) -> Optional["AccountFriendRequest"]:
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

    def _save_request(self, req, status: str, failed_reason: Optional[str] = None):
        """持久化请求状态。"""
        req.status = status
        req.failed_reason = failed_reason
        req.updated_at = datetime.now()
        FriendRequestRepository().update(req)

    def _close_modal(self, wait: float = 0.8) -> ActionResult:
        """点击关闭按钮。"""
        return tap_template_or_fallback(
            self.adb,
            self.page_detector,
            "btn_close",
            fallback_action=lambda: ActionResult.wait(wait),
            wait=wait,
        )

    def _resolve_request_friend_id(self, req) -> Optional[str]:
        """解析请求目标 friend_id。"""
        if (
            req.request_type == "add"
            and req.status == "sended"
            and req.to_account_id == self.account.id
        ):
            sender = AccountRepository().get_by_id(req.from_account_id)
            if sender and sender.friend_id:
                return sender.friend_id

        if req.to_friend_id:
            return req.to_friend_id

        if req.to_account_id:
            target = AccountRepository().get_by_id(req.to_account_id)
            if target and target.friend_id:
                return target.friend_id
        return None

    def _extract_nickname_from_ocr(
        self,
        ocr_results: list[dict],
        target_friend_id: Optional[str],
    ) -> Optional[str]:
        """从搜索结果 OCR 中提取目标昵称（Lv 下方）。"""
        return extract_nickname_by_lv(
            ocr_results=ocr_results,
            search_range_y=self.adb.scaled_y(300),
            excluded_contains=get_text_patterns("profile_exclude"),
        )

    def _save_target_nickname(self, req, ocr_results: list[dict]):
        """保存好友请求与交换请求的目标昵称。"""
        if req.request_type != "add" or req.status != "sending":
            return
        target_friend_id = self._resolve_request_friend_id(req)
        nickname = self._extract_nickname_from_ocr(ocr_results, target_friend_id)
        if not nickname:
            return
        if req.to_nickname == nickname:
            return

        req.to_nickname = nickname
        FriendRequestRepository().update(req)

        if target_friend_id and self.account.id is not None:
            ExchangeCardRequestRepository().update_active_nickname(
                from_account_id=self.account.id,
                to_friend_id=target_friend_id,
                to_nickname=nickname,
            )

    def _get_search_icon_box(self) -> Optional[tuple[int, int, int, int]]:
        """获取搜索按钮模板框。"""
        box = self.page_detector.find_template("icon_search", threshold=0.8)
        if box:
            return box
        match = self.page_detector.find_template_with_scale(
            "icon_search", scale=1.0, threshold=0.8
        )
        if match:
            return match.box
        return None

    def _get_search_input_focus_point(self) -> Optional[tuple[int, int]]:
        """根据搜索按钮获取输入框坐标。"""
        icon_box = self._get_search_icon_box()
        if icon_box is None:
            return None
        return self.adb.center_x(), (icon_box[1] + icon_box[3]) // 2

    def _find_green_yes_match(self):
        """查找绿色勾模板。"""
        match = self.page_detector.find_template_with_scale(
            "icon_green_yes", scale=1.0, threshold=0.8
        )
        if match:
            return match
        return self.page_detector.find_template_with_scale(
            "icon_green_yes", scale=0.8, threshold=0.8
        )

    def _find_green_yes_match_by_scale(self, scale: float):
        """按指定缩放比例查找绿色勾模板。"""
        return self.page_detector.find_template_with_scale(
            "icon_green_yes", scale=scale, threshold=0.8
        )

    def _find_red_no_match(self):
        """查找红色叉模板。"""
        match = self.page_detector.find_template_with_scale(
            "icon_red_no", scale=1.0, threshold=0.8
        )
        if match:
            return match
        return self.page_detector.find_template_with_scale(
            "icon_red_no", scale=0.8, threshold=0.8
        )

    def _find_red_no_match_by_scale(self, scale: float):
        """按指定缩放比例查找红色叉模板。"""
        return self.page_detector.find_template_with_scale(
            "icon_red_no", scale=scale, threshold=0.8
        )

    def _is_pending_reply_by_icons(self) -> bool:
        """1.0 模板下同时有绿色勾和红色叉，判定为待回复状态。"""
        green_1x = self._find_green_yes_match_by_scale(1.0)
        red_1x = self._find_red_no_match_by_scale(1.0)
        return green_1x is not None and red_1x is not None

    def _is_already_friend_by_icons(self) -> bool:
        """0.8 模板下命中绿色勾，判定为已是好友状态。"""
        green_08 = self._find_green_yes_match_by_scale(0.8)
        return green_08 is not None

    def _is_friend_confirmed_by_icons(self, request_id: Optional[int] = None) -> bool:
        """仅当存在绿色勾且不存在红叉时，判定为已确认好友。"""
        green_match = self._find_green_yes_match()
        red_match = self._find_red_no_match()

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

    def _handle_home(self, page_info: dict) -> ActionResult:
        """主页点击社群。"""
        if self._completed:
            return ActionResult.ok(wait=0.5)
        return tap_community_icon(self.adb, self.page_detector)

    def _handle_community(self, page_info: dict) -> ActionResult:
        """社群页点击朋友入口。"""
        result = tap_text_exact(
            self.adb,
            page_info.get("ocr_results", []),
            get_text_patterns("friend_tab_friends"),
            wait=1.0,
        )
        return result or ActionResult.wait(0.8)

    def _handle_friend_list(self, page_info: dict) -> ActionResult:
        """好友列表页统一进入搜索入口。"""
        if self._completed:
            return ActionResult.ok(wait=0.5)
        req = self._pick_current_request()
        if req is None:
            self._completed = True
            return ActionResult.ok(wait=0.5)
        return tap_template_or_fallback(
            self.adb,
            self.page_detector,
            "icon_add_friends",
            fallback_action=lambda: ActionResult.wait(0.8),
            wait=0.9,
        )

    def _handle_search_modal(self, page_info: dict) -> ActionResult:
        """搜索页：每个请求强制执行 清空->输入->搜索。"""
        req = self._pick_current_request()
        if req is None:
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
            self._reset_action_cache()
            self._add_apply_wait_rounds = 0
            self._cancel_wait_rounds = 0
            self._accept_wait_rounds = 0
            self._delete_wait_rounds = 0

        focus_point = self._get_search_input_focus_point()
        if focus_point is None:
            return ActionResult.wait(0.5)

        if not self._is_action_done("search_cleared"):
            logger.debug("请求 %s: 强制清空输入框", request_id)
            clear_text(self.adb, focus_point[0], focus_point[1], max_chars=24, wait=0.2)
            self._mark_action_done("search_cleared")
            return ActionResult.wait(0.4)

        if not self._is_action_done("search_input_done"):
            logger.debug(
                "请求 %s: 强制输入目标friend_id=%s", request_id, target_friend_id
            )
            input_text(self.adb, target_friend_id, wait=0.3)
            self._mark_action_done("search_input_done")
            return ActionResult.wait(0.6)

        if not self._is_action_done("search_submitted"):
            logger.info("请求 %s: 点击icon_search执行查询", request_id)
            result = tap_template(self.adb, self.page_detector, "icon_search", wait=0.9)
            if result:
                self._mark_action_done("search_submitted")
                self._submitted_request_id = request_id
                return result
            return ActionResult.wait(0.8)

        return ActionResult.wait(0.6)

    def _handle_search_result(self, page_info: dict) -> ActionResult:
        """搜索结果页统一处理三类请求。"""
        req = self._pick_current_request()
        if req is None:
            return ActionResult.wait(0.5)

        # 关键约束：切换请求后，不复用旧搜索结果，先关闭结果页回到搜索输入页重搜
        if req.id != self._active_request_id:
            self._active_request_id = req.id
            self._submitted_request_id = None
            self._reset_action_cache()
            self._add_apply_wait_rounds = 0
            self._cancel_wait_rounds = 0
            self._accept_wait_rounds = 0
            self._delete_wait_rounds = 0
            logger.debug("请求已切换，关闭当前搜索结果，回到搜索页重查目标friend_id")
            return self._close_modal(wait=0.8)

        # 严格约束：只有当前请求主动点过搜索按钮后，才能消费搜索结果。
        # 否则该结果视为“上一请求残留结果”，必须先关闭回到搜索页。
        if self._submitted_request_id != req.id:
            logger.debug("检测到残留搜索结果，先关闭后再按当前请求重新搜索")
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
            # 外部好友不创建 FriendshipRepository，等待对方接受后再确认
            self._refresh_requests()
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
            self._mark_action_done("add_apply_clicked")
            self._add_apply_wait_rounds = 0
            return apply_result

        if not self._is_action_done("add_apply_clicked"):
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
            FriendshipRepository().create(
                current_account_id, req.to_friend_id, req.to_account_id
            )

        # 若有目标账号信息，尝试补齐双向关系
        if req.to_account_id:
            target = AccountRepository().get_by_id(req.to_account_id)
            if target and target.friend_id:
                FriendshipRepository().create(
                    current_account_id, target.friend_id, target.id
                )
            if target and target.id and self.account.friend_id:
                FriendshipRepository().create(
                    target.id,
                    self.account.friend_id,
                    current_account_id,
                )

    def _handle_add_sended_result(self, req, page_info: dict) -> ActionResult:
        """处理接受好友请求结果（系统内）或确认外部好友是否已接受。"""
        ocr_results = page_info.get("ocr_results", [])

        # 外部好友：to_account_id 为 null，检查是否已是好友
        if req.to_account_id is None:
            return self._handle_external_sended_result(req, page_info)

        # 系统内好友：接受对方发来的请求
        if not self._is_action_done("accept_green_clicked"):
            green_click_result = self._tap_green_yes(wait=0.8)
            if green_click_result:
                self._mark_action_done("accept_green_clicked")
                return green_click_result

        if self._is_action_done("accept_green_clicked"):
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
                FriendshipRepository().create(
                    self.account.id, req.to_friend_id, req.to_account_id
                )
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

        if not self._is_action_done("delete_green_clicked"):
            green_click_result = self._tap_green_yes(wait=0.8)
            if green_click_result:
                self._mark_action_done("delete_green_clicked")
                return green_click_result

        if self._is_action_done("delete_green_clicked"):
            return ActionResult.wait(0.6)

        self._delete_wait_rounds += 1
        if self._delete_wait_rounds >= MAX_WAIT_ROUNDS_DELETE:
            self._save_request(
                req, "failed", failed_reason="删除结果页未出现绿色勾或申请"
            )
            self._refresh_requests()
            return self._close_modal(wait=0.8)
        return ActionResult.wait(0.8)

    def _handle_remove_confirm(self, page_info: dict) -> ActionResult:
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

        sender = AccountRepository().get_by_id(req.from_account_id)
        if sender is None or sender.id is None or not sender.friend_id:
            self._save_request(req, "failed", failed_reason="发送方账号信息不完整")
            self._refresh_requests()
            return

        self._save_request(req, "completed")
        FriendshipRepository().create(current_account_id, sender.friend_id, sender.id)
        if self.account.friend_id:
            FriendshipRepository().create(
                sender.id, self.account.friend_id, current_account_id
            )
        self._refresh_requests()
