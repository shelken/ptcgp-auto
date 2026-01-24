# -*- coding: utf-8 -*-
"""
账号信息获取任务

从游戏 UI 获取账号的 friend_id 和 nickname，更新到数据库。
"""

import logging
import re
from enum import Enum, auto
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
    press_back,
    tap_home_icon,
    tap_above_point,
    tap_top_center,
)

logger = logging.getLogger(__name__)

# ============================================================
# 常量定义（基于 1080x1920 基准分辨率的像素值）
# 使用时通过 adb.scaled_x/scaled_y 缩放到当前分辨率
# ============================================================

# 头像点击位置：Lv. 文字上方的偏移量（从截图测量：约 150px）
BASE_AVATAR_OFFSET_Y = 150

# 备用点击位置（未找到 Lv. 时，屏幕上方区域）
BASE_FALLBACK_TAP_Y = 300

# nickname 搜索范围：Lv.(y≈778) 到 nickname(y≈940) 约 160px，取 300 留余量
BASE_NICKNAME_SEARCH_RANGE = 300

# 最小 Y 坐标，防止点到屏幕外
MIN_TAP_Y = 50

# friend_id 格式：XXXX-XXXX-XXXX-XXXX
FRIEND_ID_PATTERN = re.compile(r"\d{4}-\d{4}-\d{4}-\d{4}")

# level 格式：Lv. 或 Lv 后跟数字
LEVEL_PATTERN = re.compile(r"Lv\.?\s*(\d+)")


class FetchPhase(Enum):
    """任务阶段"""

    INIT = auto()  # 初始化
    NAVIGATING_TO_HOME = auto()  # 导航到主页
    AT_HOME = auto()  # 在主页
    ENTERING_PROFILE = auto()  # 进入个人资料页
    AT_PROFILE = auto()  # 在个人资料页
    DONE = auto()  # 完成


def _get_patterns(key: str) -> list[str]:
    """获取指定配置的文本列表"""
    patterns = TEXT_PATTERNS.get(key, [])
    if isinstance(patterns, list):
        return patterns
    return []


# ============================================================
# 页面识别规则
# 注意：priority 数值越小优先级越高
# ============================================================
FETCH_PAGES = [
    {
        "name": "game_home_main",
        "match_all": True,
        "identifiers": _get_patterns("game_home_main"),
        "priority": 99,
    },
    {
        "name": "profile_page",
        "identifiers": _get_patterns("profile_page"),
        "priority": 99,
    },
    {
        "name": "home_icon",
        "templates": ["icon_home"],
        "priority": 50,
    },
]


# ============================================================
# 任务实现
# ============================================================


@TaskRegistry.register("fetch_account_info")
class FetchAccountInfoTask(Task):
    """
    账号信息获取任务

    从游戏 UI 中获取 friend_id、nickname 和 level，更新到数据库。
    适用于账号缺少这些信息时自动补全。
    """

    task_type = "fetch_account_info"
    reset_type = ResetType.ONCE  # 只执行一次
    pages = FETCH_PAGES  # 任务专用页面规则

    @staticmethod
    def needs_fetch(account) -> bool:
        """
        检查账号是否需要获取信息

        Args:
            account: Account 对象

        Returns:
            True 如果缺少 friend_id、nickname 或 level 中的任意一个
        """
        return not account.friend_id or not account.nickname or not account.level

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._phase = FetchPhase.INIT
        self._fetched_friend_id: Optional[str] = None
        self._fetched_nickname: Optional[str] = None
        self._fetched_level: Optional[int] = None
        self._max_attempts = 3
        self._attempt_count = 0

    def setup(self) -> bool:
        """初始化任务"""
        # 注意：页面规则通过 pages 类属性定义，由 executor 统一加载
        self._phase = FetchPhase.NAVIGATING_TO_HOME
        logger.debug("开始获取账号信息任务")
        return True

    def cleanup(self):
        """清理任务"""
        # 注意：页面规则由 executor 统一清理
        pass

    def is_completed(self) -> bool:
        """检查任务是否完成"""
        return self._phase == FetchPhase.DONE

    def check_completion(self) -> Optional[TaskResult]:
        """检查任务完成状态并返回结果"""
        if self._phase == FetchPhase.DONE:
            if self._fetched_friend_id or self._fetched_nickname or self._fetched_level:
                return TaskResult.ok(
                    message=f"已获取账号信息: friend_id={self._fetched_friend_id}, nickname={self._fetched_nickname}, level={self._fetched_level}"
                )
            else:
                return TaskResult.fail("未能获取账号信息")

        if self._attempt_count >= self._max_attempts:
            return TaskResult.fail("超过最大尝试次数")

        return None

    def handle_page(self, page_name: str, page_info: dict) -> ActionResult:
        """处理页面（抽象方法实现）"""
        return self.process_page(page_info)

    def process_page(self, page_info: dict) -> ActionResult:
        """处理页面"""
        page_name = page_info.get("name", "unknown")

        logger.debug(f"[FetchAccountInfo] 页面: {page_name}, 阶段: {self._phase.name}")

        # 主页
        if page_name == "game_home_main":
            return self._handle_home(page_info)

        # 个人资料页
        if page_name == "profile_page":
            return self._handle_profile(page_info)

        # home_icon - 可以点击回主页
        if page_name == "home_icon":
            return self._handle_home_icon(page_info)

        # 未知页面：不主动按返回，让 common_handlers 或 task_base 框架处理
        # 返回等待结果，让框架继续循环
        logger.debug(f"[FetchAccountInfo] 未处理页面: {page_name}，等待框架处理")
        return ActionResult.ok(wait=1.0)

    def _handle_home(self, page_info: dict) -> ActionResult:
        """处理主页"""
        self._phase = FetchPhase.AT_HOME
        ocr_results = page_info.get("ocr_results", [])

        # 查找 Lv. 文本位置，点击其上方进入个人资料页
        lv_pos = self._find_lv_position(ocr_results)
        if lv_pos:
            # 点击 Lv. 上方区域（头像位置）
            logger.debug("  -> 点击头像区域进入个人资料")
            self._phase = FetchPhase.ENTERING_PROFILE
            return tap_above_point(
                self.adb,
                lv_pos,
                base_offset_y=BASE_AVATAR_OFFSET_Y,
                min_y=MIN_TAP_Y,
                wait=1.0,
            )

        # 没找到 Lv.，尝试点击屏幕中上方
        logger.debug("  -> 未找到 Lv.，点击中上方")
        self._phase = FetchPhase.ENTERING_PROFILE
        return tap_top_center(self.adb, BASE_FALLBACK_TAP_Y, wait=2.0)

    def _handle_profile(self, page_info: dict) -> ActionResult:
        """处理个人资料页"""
        self._phase = FetchPhase.AT_PROFILE
        ocr_results = page_info.get("ocr_results", [])

        # 提取 friend_id
        friend_id = self._extract_friend_id(ocr_results)
        if friend_id:
            self._fetched_friend_id = friend_id
            logger.debug(f"  -> 获取到 friend_id: {friend_id}")

        # 提取 level
        level = self._extract_level(ocr_results)
        if level:
            self._fetched_level = level
            logger.debug(f"  -> 获取到 level: {level}")

        # 提取 nickname
        nickname = self._extract_nickname(ocr_results)
        if nickname:
            self._fetched_nickname = nickname
            logger.debug(f"  -> 获取到 nickname: {nickname}")

        # 更新数据库
        self._update_account()

        # 返回主页
        self._phase = FetchPhase.DONE
        logger.debug("  -> 获取完成，返回主页")
        return press_back(self.adb)

    def _handle_home_icon(self, page_info: dict) -> ActionResult:
        """处理有 home_icon 的页面"""
        logger.debug("  -> 点击 Home 图标返回主页")
        return tap_home_icon(self.adb, self.page_detector)

    def _box_center(self, box: tuple) -> tuple:
        """计算边界框中心点"""
        x1, y1, x2, y2 = box
        return ((x1 + x2) // 2, (y1 + y2) // 2)

    def _find_lv_position(self, ocr_results: list) -> Optional[tuple]:
        """查找 Lv. 文本位置"""
        for item in ocr_results:
            text = item["text"]
            if text.startswith("Lv.") or text.startswith("Lv "):
                return self._box_center(item["box"])
        return None

    def _extract_friend_id(self, ocr_results: list) -> Optional[str]:
        """从 OCR 结果提取 friend_id"""
        for item in ocr_results:
            match = FRIEND_ID_PATTERN.search(item["text"])
            if match:
                return match.group()
        return None

    def _extract_level(self, ocr_results: list) -> Optional[int]:
        """从 OCR 结果提取等级"""
        for item in ocr_results:
            match = LEVEL_PATTERN.search(item["text"])
            if match:
                try:
                    return int(match.group(1))
                except ValueError:
                    continue
        return None

    def _extract_nickname(self, ocr_results: list) -> Optional[str]:
        """
        从 OCR 结果提取 nickname

        个人资料页布局（从上到下）：
        - 朋友ID 区域
        - 头像 + Lv. 区域
        - 昵称区域（在 Lv. 下方）
        - 战绩/勋章等

        nickname 在 Lv. 下方、战绩上方
        """
        # 找到 Lv. 位置作为参考点
        lv_y = None

        for item in ocr_results:
            text = item["text"]
            if text.startswith("Lv.") or text.startswith("Lv "):
                lv_y = self._box_center(item["box"])[1]
                break

        if lv_y is None:
            return None

        # 计算搜索范围（使用基准像素 + 缩放）
        search_range = self.adb.scaled_y(BASE_NICKNAME_SEARCH_RANGE)

        # 从 locales 获取排除文本
        exclude_patterns = _get_patterns("profile_exclude")

        candidates = []
        for item in ocr_results:
            text = item["text"]
            y = self._box_center(item["box"])[1]
            # 在 Lv. 下方指定范围内搜索
            # 排除经验值（如 1,610/1,865）和其他固定文本
            if lv_y < y < lv_y + search_range:
                is_excluded = any(p in text for p in exclude_patterns)
                # 排除经验值格式（数字/数字）
                is_exp_format = "/" in text and text.replace(",", "").replace("/", "").replace(".", "").isdigit()
                is_pure_numeric = text.replace(",", "").replace(".", "").isdigit()
                if not is_excluded and not is_exp_format and not is_pure_numeric and len(text) >= 2:
                    candidates.append((text, y))

        if candidates:
            # 取 Lv. 下方最近的文本（跳过经验值后的第一个）
            candidates.sort(key=lambda x: x[1])
            return candidates[0][0]

        return None

    def _update_account(self):
        """更新账号信息到数据库"""
        if not self.account:
            logger.warning("无账号信息，跳过更新")
            return

        updated = False

        if self._fetched_friend_id and self.account.friend_id != self._fetched_friend_id:
            self.account.friend_id = self._fetched_friend_id
            updated = True

        if self._fetched_nickname and self.account.nickname != self._fetched_nickname:
            self.account.nickname = self._fetched_nickname
            updated = True

        if self._fetched_level and self.account.level != self._fetched_level:
            self.account.level = self._fetched_level
            updated = True

        if updated:
            from ptcgp_auto_v2.db.repositories import AccountRepository

            repo = AccountRepository()
            repo.update(self.account)
            logger.info(
                f"已更新账号信息: friend_id={self.account.friend_id}, "
                f"nickname={self.account.nickname}, level={self.account.level}"
            )
