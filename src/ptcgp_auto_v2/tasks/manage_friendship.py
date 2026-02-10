# -*- coding: utf-8 -*-
"""
管理好友关系任务。

统一通过“搜索入口”处理三类请求：
- add + sending: 发送好友请求
- add + sended: 接受好友请求
- delete + deleting: 删除好友
"""

import logging
import re
from datetime import datetime
from typing import TYPE_CHECKING, Optional

from ptcgp_auto_v2.core.task_base import ActionResult, ResetType, Task, TaskRegistry
from ptcgp_auto_v2.db.repositories import (
    AccountRepository,
    FriendRequestRepository,
    FriendshipRepository,
    TaskInstanceRepository,
)
from ptcgp_auto_v2.locales import get_text_patterns
from ptcgp_auto_v2.utils.gesture import (
    clear_text,
    input_text,
    is_text_visible,
    tap_box,
    tap_community_icon,
    tap_ok,
    tap_template,
    tap_text_exact,
)

logger = logging.getLogger(__name__)
FRIEND_ID_PATTERN = re.compile(r"\d{4}-\d{4}-\d{4}-\d{4}")

if TYPE_CHECKING:
    from ptcgp_auto_v2.db.models import AccountFriendRequest


def _build_manage_friendship_pages() -> list[dict]:
    """构建好友任务页面规则。"""
    return [
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
            "name": "friend_list",
            "identifiers": get_text_patterns("friend_page_list"),
            "match_all": True,
            "priority": 90,
        },
        {
            "name": "friend_search_modal",
            "templates": ["icon_search"],
            "priority": 90,
        },
        {
            "name": "friend_search_result_modal",
            "identifiers": get_text_patterns("friend_page_search_result"),
            "priority": 91,
        },
        {
            "name": "friend_remove_confirm",
            "identifiers": get_text_patterns("friend_remove_confirm_title"),
            "priority": 95,
        },
    ]


@TaskRegistry.register("manage_friendship")
class ManageFriendshipTask(Task):
    """好友请求统一处理任务。"""

    task_type = "manage_friendship"
    reset_type = ResetType.ONCE
    pages = _build_manage_friendship_pages()
    max_unknown_pages = 20

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

        self.requests_to_process = self._get_pending_requests()
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
            self._completed = True
            logger.info("没有待处理的好友请求，任务完成")

    def is_completed(self) -> bool:
        """返回任务是否完成。"""
        return self._completed

    def handle_page(self, page_name: str, page_info: dict) -> ActionResult:
        """按页面分发处理。"""
        if page_name != self._last_page_name:
            self._reset_action_cache()
            self._last_page_name = page_name

        handlers = {
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
        """读取当前账号待处理请求。"""
        if self.account.id is None:
            return []
        repo = FriendRequestRepository()
        sending = repo.get_by_from_account_and_status(self.account.id, "sending")
        sended = repo.get_by_to_account_and_status(self.account.id, "sended")
        canceling = repo.get_by_from_account_and_type(
            self.account.id, "add", "canceling"
        )
        deleting = repo.get_by_from_account_and_type(
            self.account.id, "delete", "deleting"
        )
        return list(sending) + list(sended) + list(canceling) + list(deleting)

    def _refresh_requests(self):
        """刷新请求列表。"""
        self.requests_to_process = self._get_pending_requests()
        self.current_request = None
        self._active_request_id = None
        self._submitted_request_id = None
        if not self.requests_to_process:
            self._completed = True

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
        result = tap_template(self.adb, self.page_detector, "btn_close", wait=wait)
        return result or ActionResult.wait(wait)

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

    def _extract_friend_id_from_text(self, text: str) -> Optional[str]:
        """从文本提取标准 friend_id。"""
        match = FRIEND_ID_PATTERN.search(text)
        if not match:
            return None
        return match.group().replace("-", "")

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

    def _extract_search_input_friend_id(self, ocr_results: list[dict]) -> Optional[str]:
        """读取当前输入框 friend_id。"""
        icon_box = self._get_search_icon_box()
        if icon_box is None:
            return None
        icon_left = icon_box[0]
        anchor_y = (icon_box[1] + icon_box[3]) // 2
        y_threshold = self.adb.scaled_y(140)

        candidates: list[tuple[int, str]] = []
        for item in ocr_results:
            friend_id = self._extract_friend_id_from_text(str(item.get("text", "")))
            if not friend_id:
                continue
            box = item.get("box")
            if not box:
                continue
            text_x = (box[0] + box[2]) // 2
            text_y = (box[1] + box[3]) // 2
            if text_x >= icon_left or abs(text_y - anchor_y) > y_threshold:
                continue
            distance = abs(text_y - anchor_y) + abs(icon_left - text_x)
            candidates.append((distance, friend_id))

        if not candidates:
            return None
        candidates.sort(key=lambda x: x[0])
        return candidates[0][1]

    def _tap_apply_button(self, ocr_results: list[dict]) -> Optional[ActionResult]:
        """点击申请按钮。"""
        patterns = {
            "".join(t.lower().split()) for t in get_text_patterns("friend_apply_button")
        }
        for item in ocr_results:
            text = "".join(str(item.get("text", "")).lower().split())
            if text not in patterns:
                continue
            box = item.get("box")
            if not box:
                continue
            tap_x = min(
                self.adb.screen_width - 1,
                (box[0] + box[2]) // 2 + self.adb.scaled_x(24),
            )
            tap_y = (box[1] + box[3]) // 2
            self.adb.tap(tap_x, tap_y)
            logger.debug("点击申请按钮: (%s, %s)", tap_x, tap_y)
            return ActionResult.ok(wait=0.9)
        return None

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

    def _handle_home(self, page_info: dict) -> ActionResult:
        """主页点击社群。"""
        if self._completed:
            return ActionResult.ok(wait=0.5)
        return tap_community_icon(self.adb, self.page_detector, wait=1.0)

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
        result = tap_template(
            self.adb, self.page_detector, "icon_add_friends", wait=0.9
        )
        return result or ActionResult.wait(0.8)

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
            logger.debug("请求 %s: 点击icon_search执行查询", request_id)
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
            self._save_request(req, "sended")
            if req.to_account_id:
                TaskInstanceRepository().update_status_to_pending(
                    req.to_account_id, "manage_friendship"
                )
            else:
                self._save_request(req, "completed")
                if req.to_friend_id and self.account.id is not None:
                    FriendshipRepository().create(
                        self.account.id, req.to_friend_id, req.to_account_id
                    )
            self._refresh_requests()
            return self._close_modal(wait=0.8)

        if not self._is_action_done("add_apply_clicked"):
            apply_result = self._tap_apply_button(ocr_results)
            if apply_result:
                self._mark_action_done("add_apply_clicked")
                self._add_apply_wait_rounds = 0
                return apply_result

        self._add_apply_wait_rounds += 1
        if self._add_apply_wait_rounds >= 6:
            self._save_request(req, "failed", failed_reason="发送后未出现取消交友邀请")
            self._refresh_requests()
            return self._close_modal(wait=0.8)
        return ActionResult.wait(0.8)

    def _handle_add_sended_result(self, req, page_info: dict) -> ActionResult:
        """处理接受好友请求结果。"""
        if not self._is_action_done("accept_green_clicked"):
            green_match = self._find_green_yes_match()
            if green_match:
                self._mark_action_done("accept_green_clicked")
                return tap_box(self.adb, green_match.box, wait=0.8)

        if self._is_action_done("accept_green_clicked"):
            close_result = self._close_modal(wait=0.8)
            if close_result.success:
                self._complete_add_sended_request(req)
            return close_result

        self._accept_wait_rounds += 1
        if self._accept_wait_rounds >= 6:
            self._save_request(req, "failed", failed_reason="接受流程未找到绿色勾")
            self._refresh_requests()
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

        if not self._is_action_done("cancel_request_clicked"):
            cancel_result = tap_text_exact(
                self.adb,
                ocr_results,
                get_text_patterns("friend_cancel_request"),
                wait=0.8,
            )
            if cancel_result:
                self._mark_action_done("cancel_request_clicked")
                self._cancel_wait_rounds = 0
                return cancel_result

        self._cancel_wait_rounds += 1
        if self._cancel_wait_rounds >= 6:
            self._save_request(req, "failed", failed_reason="取消邀请后未出现申请按钮")
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
            green_match = self._find_green_yes_match()
            if green_match:
                self._mark_action_done("delete_green_clicked")
                return tap_box(self.adb, green_match.box, wait=0.8)

        if self._is_action_done("delete_green_clicked"):
            return ActionResult.wait(0.6)

        self._delete_wait_rounds += 1
        if self._delete_wait_rounds >= 6:
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
