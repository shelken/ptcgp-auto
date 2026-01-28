# -*- coding: utf-8 -*-
"""
账号信息获取任务

从游戏 UI 获取 friend_id、nickname、level、exchange_points，更新到数据库。

流程：主页 → 个人资料页 → 返回 → 社群页面 → 交换页面 → 返回 → 完成
"""

import logging
import re
from typing import Optional

from ptcgp_auto_v2.core.task_base import (
    ActionResult,
    ResetType,
    Task,
    TaskRegistry,
    TaskResult,
)
from ptcgp_auto_v2.locales.zh_Hant import TEXT_PATTERNS
from ptcgp_auto_v2.utils.gesture import (
    navigate_back,
    tap_home_icon,
    tap_community_icon,
    tap_above_point,
    tap_top_center,
    tap_text,
)

logger = logging.getLogger(__name__)

# 基准像素值（1080x1920）
BASE_AVATAR_OFFSET_Y = 150  # 头像在 Lv. 上方的偏移
BASE_FALLBACK_TAP_Y = 300   # 备用点击位置
MIN_TAP_Y = 50

# 正则
FRIEND_ID_PATTERN = re.compile(r"\d{4}-\d{4}-\d{4}-\d{4}")
LEVEL_PATTERN = re.compile(r"Lv\.?\s*(\d+)")


def _get_patterns(key: str) -> list[str]:
    return TEXT_PATTERNS.get(key, [])


# 页面识别规则
FETCH_PAGES = [
    {"name": "game_home_main", "match_all": True, "identifiers": _get_patterns("game_home_main"), "priority": 10},
    {"name": "profile_page", "identifiers": _get_patterns("profile_page"), "priority": 20},
    {"name": "community_page", "identifiers": _get_patterns("community_page"), "match_all": True, "priority": 25},
    {"name": "exchange_locked_popup", "identifiers": _get_patterns("exchange_locked_popup"), "priority": 28},
    {"name": "exchange_page", "identifiers": _get_patterns("exchange_page"), "priority": 30},
    {"name": "home_icon", "templates": ["icon_home"], "priority": 50},
]


@TaskRegistry.register("fetch_account_info")
class FetchAccountInfoTask(Task):
    """账号信息获取任务"""

    task_type = "fetch_account_info"
    reset_type = ResetType.ONCE
    pages = FETCH_PAGES

    @staticmethod
    def needs_fetch(account) -> bool:
        return not account.friend_id or not account.nickname or account.exchange_points is None

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._profile_done = False
        self._exchange_done = False
        self._friend_id: Optional[str] = None
        self._nickname: Optional[str] = None
        self._level: Optional[int] = None
        self._exchange_points: Optional[int] = None
        self._done = False

    def setup(self) -> bool:
        return True

    def cleanup(self):
        pass

    def is_completed(self) -> bool:
        return self._done

    def check_completion(self) -> Optional[TaskResult]:
        if self._done:
            if self._friend_id or self._nickname or self._exchange_points is not None:
                return TaskResult.ok(
                    message=f"获取完成: friend_id={self._friend_id}, nickname={self._nickname}, "
                    f"level={self._level}, exchange_points={self._exchange_points}"
                )
            return TaskResult.fail("未能获取账号信息")
        return None

    def handle_page(self, page_name: str, page_info: dict) -> ActionResult:
        """按页面分发到处理函数"""
        handlers = {
            "game_home_main": self._handle_home,
            "profile_page": self._handle_profile,
            "community_page": self._handle_community,
            "exchange_page": self._handle_exchange,
            "exchange_locked_popup": self._handle_exchange_locked,
        }

        handler = handlers.get(page_name)
        if handler:
            return handler(page_info)

        # 兜底：先尝试点主页图标，找不到再用返回
        result = tap_home_icon(self.adb, self.page_detector, wait=3)
        if result and result.success:
            return result
        return navigate_back(self.adb, self.page_detector,
            page_info.get("ocr_results", []), _get_patterns("back_button"))

    def _handle_home(self, page_info: dict) -> ActionResult:
        """主页：根据进度决定下一步"""
        ocr = page_info.get("ocr_results", [])

        if not self._profile_done:
            # 第一步：进入个人资料页
            return self._enter_profile(ocr)

        if not self._exchange_done:
            # 第二步：进入社群页面
            logger.debug("  -> 点击社群图标")
            return tap_community_icon(self.adb, self.page_detector, wait=5.0)

        # 都完成了
        self._update_account()
        self._done = True
        logger.debug("  -> 任务完成")
        return ActionResult.ok(wait=0.5)

    def _handle_profile(self, page_info: dict) -> ActionResult:
        """个人资料页：提取信息后标记完成"""
        ocr = page_info.get("ocr_results", [])

        # 提取信息
        for item in ocr:
            text = item["text"]
            if not self._friend_id:
                m = FRIEND_ID_PATTERN.search(text)
                if m:
                    self._friend_id = m.group()
                    logger.debug(f"  -> friend_id: {self._friend_id}")
            if not self._level:
                m = LEVEL_PATTERN.search(text)
                if m:
                    self._level = int(m.group(1))
                    logger.debug(f"  -> level: {self._level}")

        if not self._nickname:
            self._nickname = self._extract_nickname(ocr)
            if self._nickname:
                logger.debug(f"  -> nickname: {self._nickname}")

        self._profile_done = True
        logger.debug("  -> 资料获取完成，返回")
        return navigate_back(self.adb, self.page_detector, ocr, _get_patterns("back_button"))

    def _handle_community(self, page_info: dict) -> ActionResult:
        """社群页面：点击交换按钮或返回主页"""
        # 如果已获取交换点数，直接回主页
        if self._exchange_done:
            return tap_home_icon(self.adb, self.page_detector, wait=1.5)

        ocr = page_info.get("ocr_results", [])
        result = tap_text(self.adb, ocr, _get_patterns("community_exchange_btn"), wait=2.0)
        if result:
            logger.debug("  -> 点击交換按钮")
            return result
        return ActionResult.ok(wait=1.0)

    def _handle_exchange(self, page_info: dict) -> ActionResult:
        """交换页面：提取点数后标记完成"""
        ocr = page_info.get("ocr_results", [])

        points = self._extract_exchange_points(ocr)
        if points is not None:
            self._exchange_points = points
            logger.debug(f"  -> exchange_points: {points}")

        self._exchange_done = True
        logger.debug("  -> 交换点数获取完成，返回")
        return navigate_back(self.adb, self.page_detector, ocr, _get_patterns("back_button"))

    def _handle_exchange_locked(self, page_info: dict) -> ActionResult:
        """交换未解锁弹窗：点击OK并标记完成"""
        ocr = page_info.get("ocr_results", [])

        # 标记为 0 表示未解锁
        self._exchange_points = 0
        self._exchange_done = True
        logger.info("  -> 交换功能未解锁，标记完成")

        # 点击 OK 关闭弹窗
        result = tap_text(self.adb, ocr, _get_patterns("popup_ok"), wait=2.0)
        if result:
            return result
        return ActionResult.ok(wait=1.0)

    def _enter_profile(self, ocr: list) -> ActionResult:
        """点击头像进入个人资料"""
        lv_pos = self._find_lv_position(ocr)
        if lv_pos:
            logger.debug("  -> 点击头像区域")
            return tap_above_point(self.adb, lv_pos, BASE_AVATAR_OFFSET_Y, MIN_TAP_Y, wait=5.0)
        logger.debug("  -> 未找到 Lv.，点击中上方")
        return tap_top_center(self.adb, BASE_FALLBACK_TAP_Y, wait=2.0)

    def _find_lv_position(self, ocr: list) -> Optional[tuple]:
        for item in ocr:
            if item["text"].startswith("Lv"):
                box = item["box"]
                return ((box[0] + box[2]) // 2, (box[1] + box[3]) // 2)
        return None

    def _extract_nickname(self, ocr: list) -> Optional[str]:
        """从 Lv. 下方提取昵称"""
        lv_y = None
        for item in ocr:
            if item["text"].startswith("Lv"):
                box = item["box"]
                lv_y = (box[1] + box[3]) // 2
                break
        if not lv_y:
            return None

        exclude = _get_patterns("profile_exclude")
        search_range = self.adb.scaled_y(300)
        candidates = []

        for item in ocr:
            text, box = item["text"], item["box"]
            y = (box[1] + box[3]) // 2
            if lv_y < y < lv_y + search_range:
                if any(p in text for p in exclude):
                    continue
                if "/" in text and text.replace(",", "").replace("/", "").replace(".", "").isdigit():
                    continue
                if text.replace(",", "").replace(".", "").isdigit():
                    continue
                if len(text) >= 2:
                    candidates.append((text, y))

        if candidates:
            candidates.sort(key=lambda x: x[1])
            return candidates[0][0]
        return None

    def _extract_exchange_points(self, ocr: list) -> Optional[int]:
        """从交换页面提取点数（找第一个纯数字）"""
        for item in ocr:
            text = item["text"].replace(",", "").replace(" ", "")
            if text.isdigit():
                value = int(text)
                if 0 < value <= 999999:
                    return value
        return None

    def _update_account(self):
        """更新数据库"""
        if not self.account:
            return
        changed = False
        if self._friend_id and self.account.friend_id != self._friend_id:
            self.account.friend_id = self._friend_id
            changed = True
        if self._nickname and self.account.nickname != self._nickname:
            self.account.nickname = self._nickname
            changed = True
        if self._level and self.account.level != self._level:
            self.account.level = self._level
            changed = True
        if self._exchange_points is not None and self.account.exchange_points != self._exchange_points:
            self.account.exchange_points = self._exchange_points
            changed = True

        if changed:
            from ptcgp_auto_v2.db.repositories import AccountRepository
            AccountRepository().update(self.account)
            logger.info(
                f"已更新账号: friend_id={self.account.friend_id}, nickname={self.account.nickname}, "
                f"level={self.account.level}, exchange_points={self.account.exchange_points}"
            )
