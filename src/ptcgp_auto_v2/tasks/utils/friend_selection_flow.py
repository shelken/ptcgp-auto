# -*- coding: utf-8 -*-
"""
好友选择流程状态与辅助方法。

供 send_card_daily 和 exchange_cards 共用，封装：
- 好友列表选择与滑动
- 详情页验证与 nickname 提取
- 探测模式（无 nickname 时遍历）
"""

import logging
import time
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Callable, Optional

from ptcgp_auto_v2.core.task_base import ActionResult
from ptcgp_auto_v2.locales import get_text_patterns
from ptcgp_auto_v2.tasks.utils.constants import (
    BASE_FRIEND_ROW_THRESHOLD_Y,
    MAX_FRIEND_PROFILE_READ_ROUNDS,
    MAX_FRIEND_SCROLL_ROUNDS,
    MAX_FRIEND_STABLE_ROUNDS,
)
from ptcgp_auto_v2.tasks.utils.friend_card_flow import (
    build_ocr_signature,
    find_all_search_plus_boxes,
    find_send_box_near_anchor,
    find_target_search_plus_box,
    scroll_friend_list,
)
from ptcgp_auto_v2.tasks.utils.friend_id_utils import extract_friend_id_from_text
from ptcgp_auto_v2.tasks.utils.nickname_utils import extract_nickname_by_lv
from ptcgp_auto_v2.utils.gesture import click_close, tap_box

if TYPE_CHECKING:
    from ptcgp_auto_v2.infra.page_detector import PageDetector

logger = logging.getLogger(__name__)

MAX_WAIT_PROFILE_ROUNDS = 6


@dataclass
class FriendSelectionFlow:
    """好友选择流程状态。"""

    scroll_rounds: int = 0
    stable_rounds: int = 0
    last_signature: Optional[str] = None
    profile_read_rounds: int = 0
    verified_row_anchor_y: Optional[int] = None
    failed_rows: set[int] = field(default_factory=set)
    probe_boxes: list = field(default_factory=list)
    probe_index: int = 0
    friend_verified: bool = False
    nickname: Optional[str] = None
    probed_friend_ids: set[str] = field(default_factory=set)
    page_probe_start_count: int = 0
    scroll_stable_rounds: int = 0

    def reset_scroll_state(self):
        """重置滑动状态。"""
        self.scroll_rounds = 0
        self.stable_rounds = 0
        self.last_signature = None

    def reset_probe_state(self):
        """重置探测状态。"""
        self.probe_boxes = []
        self.probe_index = 0

    def record_failed_row(self):
        """记录当前失败的行。"""
        if self.verified_row_anchor_y is not None:
            self.failed_rows.add(self.verified_row_anchor_y)
        self.verified_row_anchor_y = None

    def is_in_probe_mode(self) -> bool:
        """是否处于探测模式。"""
        return self.nickname is None


class FriendSelectionHelper:
    """好友选择流程辅助类。"""

    def __init__(
        self,
        adb,
        page_detector: "PageDetector",
        flow: FriendSelectionFlow,
        target_friend_id: str,
        profile_page_name: str,
        send_text_patterns: list[str],
        account_id: Optional[int] = None,
        on_success: Optional[Callable[[], None]] = None,
        on_nickname_found: Optional[Callable[[int, str, str], None]] = None,
        on_scroll_exhausted: Optional[Callable[[str], ActionResult]] = None,
    ):
        self.adb = adb
        self.page_detector = page_detector
        self.flow = flow
        self.target_friend_id = target_friend_id
        self.profile_page_name = profile_page_name
        self.send_text_patterns = send_text_patterns
        self.account_id = account_id
        self.on_success = on_success
        self.on_nickname_found = on_nickname_found
        self.on_scroll_exhausted = on_scroll_exhausted

    def find_plus_for_nickname(
        self,
        ocr_results: list[dict],
        target_nickname: str,
    ) -> Optional[tuple[int, int, int, int]]:
        """按 nickname 找 plus（过滤 failed_rows）。"""
        if not target_nickname:
            return None

        all_plus_boxes = find_all_search_plus_boxes(self.page_detector)
        if not all_plus_boxes:
            return None

        row_threshold_y = self.adb.scaled_y(BASE_FRIEND_ROW_THRESHOLD_Y)

        available_boxes = [
            box
            for box in all_plus_boxes
            if not any(
                abs((box[1] + box[3]) // 2 - failed_y) < row_threshold_y
                for failed_y in self.flow.failed_rows
            )
        ]

        return find_target_search_plus_box(
            ocr_results=ocr_results,
            target_nickname=target_nickname,
            search_plus_boxes=available_boxes,
            row_threshold_y=row_threshold_y,
        )

    def find_send_box_by_anchor(
        self,
        ocr_results: list[dict],
    ) -> Optional[tuple[int, int, int, int]]:
        """按锚点找发送/交换按钮。"""
        return self.find_box_by_anchor(ocr_results, self.send_text_patterns)

    def find_box_by_anchor(
        self,
        ocr_results: list[dict],
        text_patterns: list[str],
    ) -> Optional[tuple[int, int, int, int]]:
        """按锚点在同一行查找指定文本框。"""
        if self.flow.verified_row_anchor_y is None:
            return None

        row_threshold_y = self.adb.scaled_y(BASE_FRIEND_ROW_THRESHOLD_Y)
        return find_send_box_near_anchor(
            ocr_results=ocr_results,
            send_text_patterns=text_patterns,
            anchor_y=self.flow.verified_row_anchor_y,
            row_threshold_y=row_threshold_y,
        )

    def check_scroll_bottom(self) -> bool:
        """检查是否滑到底部。基于已探测 friend_id 判断。"""
        return self.flow.scroll_stable_rounds >= 2

    def get_next_probe_box(self) -> Optional[tuple[int, int, int, int]]:
        """获取下一个探测用的 plus box（过滤已失败的行）。"""
        if not self.flow.probe_boxes:
            self.flow.probe_boxes = find_all_search_plus_boxes(self.page_detector)
            self.flow.probe_index = 0
            self.flow.page_probe_start_count = len(self.flow.probed_friend_ids)
            if self.flow.probe_boxes:
                logger.debug("找到 %d 个 icon_search_plus", len(self.flow.probe_boxes))
                logger.debug(
                    "开始遍历探测，共 %d 个 plus，已探测=%d",
                    len(self.flow.probe_boxes),
                    self.flow.page_probe_start_count,
                )

        row_threshold_y = self.adb.scaled_y(BASE_FRIEND_ROW_THRESHOLD_Y)

        while self.flow.probe_index < len(self.flow.probe_boxes):
            box = self.flow.probe_boxes[self.flow.probe_index]
            self.flow.probe_index += 1
            box_cy = (box[1] + box[3]) // 2
            if any(
                abs(box_cy - failed_y) < row_threshold_y
                for failed_y in self.flow.failed_rows
            ):
                logger.debug(
                    "跳过已失败的行，probe_index=%d, box_cy=%d",
                    self.flow.probe_index - 1,
                    box_cy,
                )
                continue
            logger.debug(
                "探测第 %d/%d 个 plus (y=%d)",
                self.flow.probe_index,
                len(self.flow.probe_boxes),
                box_cy,
            )
            return box

        logger.debug("本页遍历完成，需要滑动继续")
        if len(self.flow.probed_friend_ids) == self.flow.page_probe_start_count:
            self.flow.scroll_stable_rounds += 1
            logger.debug(
                "[到底检测] 本页无新好友，已探测=%d，scroll_stable_rounds=%d",
                len(self.flow.probed_friend_ids),
                self.flow.scroll_stable_rounds,
            )
        else:
            self.flow.scroll_stable_rounds = 0
        self.flow.reset_probe_state()
        return None

    def tap_plus_and_wait_profile(
        self,
        plus_box: tuple[int, int, int, int],
    ) -> ActionResult:
        """点击 plus 并主动等待 profile 页面，直接处理。"""
        self.flow.verified_row_anchor_y = (plus_box[1] + plus_box[3]) // 2
        tap_box(self.adb, plus_box, wait=1.0)

        for _ in range(MAX_WAIT_PROFILE_ROUNDS):
            page_name, page_info = self.page_detector.detect()
            if page_name == self.profile_page_name:
                return self.handle_profile_verification(
                    ocr_results=page_info.get("ocr_results", []),
                    account_id=self.account_id,
                )
            time.sleep(0.5)

        logger.warning("等待 profile 页面超时")
        self.flow.record_failed_row()
        click_close(
            self.adb,
            self.page_detector,
            [],
            get_text_patterns("text_x"),
        )
        return ActionResult.ok(wait=0.5)

    def handle_profile_verification(
        self,
        ocr_results: list[dict],
        account_id: Optional[int] = None,
    ) -> ActionResult:
        """处理详情页验证。"""
        extracted_friend_id = self._extract_friend_id(ocr_results)
        logger.debug(
            "[详情页验证] 提取 friend_id=%s, 目标=%s",
            extracted_friend_id,
            self.target_friend_id,
        )

        if not extracted_friend_id:
            self.flow.profile_read_rounds += 1
            if self.flow.profile_read_rounds < MAX_FRIEND_PROFILE_READ_ROUNDS:
                return ActionResult.wait(0.6)
            self.flow.profile_read_rounds = 0
            click_close(
                self.adb,
                self.page_detector,
                ocr_results,
                get_text_patterns("text_x"),
            )
            return ActionResult.wait(0.5)

        self.flow.probed_friend_ids.add(extracted_friend_id)

        if extracted_friend_id == self.target_friend_id:
            self.flow.friend_verified = True
            self._try_extract_and_persist_nickname(ocr_results, account_id)
            if self.on_success:
                self.on_success()
            logger.debug("好友详情核验成功：friend_id=%s", extracted_friend_id)
        else:
            self.flow.friend_verified = False
            self.flow.record_failed_row()
            logger.debug(
                "friend_id 不匹配: %s != %s",
                extracted_friend_id,
                self.target_friend_id,
            )

        self.flow.profile_read_rounds = 0
        click_close(
            self.adb,
            self.page_detector,
            ocr_results,
            get_text_patterns("text_x"),
        )
        return ActionResult.wait(0.5)

    def update_signature_and_check_stable(
        self,
        ocr_results: list[dict],
    ) -> bool:
        """更新签名并检查是否稳定。返回 True 表示已稳定。"""
        signature = build_ocr_signature(ocr_results)
        if signature == self.flow.last_signature:
            self.flow.stable_rounds += 1
        else:
            self.flow.stable_rounds = 0
            self.flow.last_signature = signature
        return self.flow.stable_rounds >= MAX_FRIEND_STABLE_ROUNDS

    def scroll_or_fail(self) -> ActionResult:
        """滑动或失败回调。"""
        logger.debug(
            "[滑动检查] stable_rounds=%d, scroll_rounds=%d, scroll_stable_rounds=%d",
            self.flow.stable_rounds,
            self.flow.scroll_rounds,
            self.flow.scroll_stable_rounds,
        )
        if self.flow.stable_rounds >= MAX_FRIEND_STABLE_ROUNDS:
            if self.on_scroll_exhausted:
                return self.on_scroll_exhausted("好友列表遍历完成未找到目标")
            return ActionResult.fail("好友列表遍历完成未找到目标")

        if self.flow.scroll_stable_rounds >= 1:
            if self.on_scroll_exhausted:
                return self.on_scroll_exhausted("已滑到底部，未找到目标好友")
            return ActionResult.fail("已滑到底部，未找到目标好友")

        self.flow.scroll_rounds += 1
        if self.flow.scroll_rounds > MAX_FRIEND_SCROLL_ROUNDS:
            if self.on_scroll_exhausted:
                return self.on_scroll_exhausted("好友列表遍历达到上限")
            return ActionResult.fail("好友列表遍历达到上限")

        self.flow.failed_rows.clear()
        self.flow.probe_boxes = []
        self.flow.probe_index = 0
        logger.debug(
            "[滑动] 执行滑动，当前轮数=%d, 已探测=%d",
            self.flow.scroll_rounds,
            len(self.flow.probed_friend_ids),
        )
        return scroll_friend_list(self.adb)

    def _extract_friend_id(self, ocr_results: list[dict]) -> Optional[str]:
        """从 OCR 结果提取 friend_id。"""
        for item in ocr_results:
            friend_id = extract_friend_id_from_text(str(item.get("text", "")))
            if friend_id:
                return friend_id
        return None

    def _try_extract_and_persist_nickname(
        self,
        ocr_results: list[dict],
        account_id: Optional[int],
    ):
        """尝试提取 nickname 并持久化。"""
        if self.flow.nickname:
            return

        nickname = extract_nickname_by_lv(
            ocr_results,
            search_range_y=self.adb.scaled_y(300),
            excluded_contains=list(get_text_patterns("profile_exclude")),
        )
        if not nickname:
            return

        self.flow.nickname = nickname
        logger.debug("探测到好友昵称: %s -> %s", self.target_friend_id, nickname)

        if self.on_nickname_found and account_id is not None:
            self.on_nickname_found(account_id, self.target_friend_id, nickname)
