# -*- coding: utf-8 -*-
"""
账号信息获取任务

从游戏 UI 获取 friend_id、nickname、level、exchange_points、pack_hourglass_count，更新到数据库。
采用字典映射处理页面，使用 action_cache 管理页面内操作状态。
流程：主页 → 个人资料页 → 返回 → 更多菜单 → 持有物页面 → 提取资源 → 返回 → 完成
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
from ptcgp_auto_v2.db.repositories import AccountRepository, AccountStatRepository
from ptcgp_auto_v2.locales import get_text_patterns
from ptcgp_auto_v2.tasks.utils.friend_id_utils import extract_friend_id_from_text
from ptcgp_auto_v2.utils.gesture import (
    navigate_back,
    quick_tap,
    scroll_points,
    swipe,
    tap_above_point,
    tap_home_icon,
    tap_template,
    tap_text,
    tap_top_center,
)

logger = logging.getLogger(__name__)

# ============================================================
# 常量定义（基于 1080x1920）
# ============================================================

# 头像在 Lv. 上方的偏移
BASE_AVATAR_OFFSET_Y = 150

# 备用点击位置
BASE_FALLBACK_TAP_Y = 300

# 最小点击 Y 坐标
MIN_TAP_Y = 50

# 持有物页面向上滑动距离（基于 1080x1920）
BASE_HOLDINGS_SCROLL_DISTANCE_Y = 260

# 持有物页面最大滑动次数
MAX_HOLDINGS_SCROLL_ROUNDS = 4

# 进入持有物页面后，至少先扫描几轮再允许滑动
MIN_HOLDINGS_SCAN_ROUNDS_BEFORE_SCROLL = 2

# 持有物列表滑动后的稳定等待时间（秒）
HOLDINGS_SCROLL_SETTLE_WAIT = 1.4

LEVEL_PATTERN = re.compile(r"Lv\.?\s*(\d+)")


# ============================================================
# 页面识别规则
# ============================================================


def _build_fetch_pages() -> list[dict]:
    """构建账号信息获取页面规则"""
    return [
        # 商店 / 得卡挑戰
        {
            "name": "game_home_main",
            "match_all": True,
            "identifiers": get_text_patterns("game_home_main"),
            "priority": 10,
        },
        # 朋友ID
        {
            "name": "profile_page",
            "identifiers": get_text_patterns("profile_page"),
            "exclude_identifiers": get_text_patterns("profile_page_exclude"),
            "priority": 20,
        },
        # 商店 / 禮物盒
        {
            "name": "more_menu_modal",
            "identifiers": get_text_patterns("more_menu_modal"),
            "match_all": True,
            "priority": 22,
        },
        # 持有物 / 寶可金塊（免費）
        {
            "name": "holdings_page",
            "identifiers": get_text_patterns("holdings_page"),
            "priority": 24,
        },
        # 開包沙漏 / 挑戰沙漏
        {
            "name": "holdings_page_scrolled",
            "identifiers": get_text_patterns("holdings_page_scrolled"),
            "priority": 24,
        },
    ]


@TaskRegistry.register("fetch_account_info")
class FetchAccountInfoTask(Task):
    """账号信息获取任务"""

    task_type = "fetch_account_info"
    reset_type = ResetType.DAILY
    screenshot_lossless = True
    pages = _build_fetch_pages()

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # 页面内操作缓存
        self._action_cache: dict[str, bool] = {}

        # 提取的信息
        self._friend_id: Optional[str] = None
        self._nickname: Optional[str] = None
        self._level: Optional[int] = None
        self._exchange_points: Optional[int] = None
        self._pack_hourglass_count: Optional[int] = None
        self._holdings_scroll_rounds = 0
        self._holdings_scan_rounds = 0

        # 任务完成标志
        self._completed = False
        self._complete_reason: Optional[str] = None

    def _is_action_done(self, key: str) -> bool:
        """检查操作是否已完成"""
        return self._action_cache.get(key, False)

    def _mark_action_done(self, key: str):
        """标记操作已完成"""
        self._action_cache[key] = True

    def _reset_action_cache(self):
        """重置操作缓存"""
        self._action_cache.clear()

    @staticmethod
    def needs_fetch(account, tasks) -> bool:
        """检查是否需要获取账号信息"""
        # 排除账号注册任务
        if any(t.task_type == "init_account" for t in tasks):
            return False

        stat = getattr(account, "account_stat", None)
        if stat is None and getattr(account, "id", None):
            stat = AccountStatRepository().get_by_account_id(int(account.id))

        exchange_points = (
            stat.exchange_points
            if stat is not None
            else getattr(account, "exchange_points", None)
        )
        pack_hourglass_count = (
            stat.pack_hourglass_count
            if stat is not None
            else getattr(account, "pack_hourglass_count", None)
        )

        return (
            not account.friend_id
            or not account.nickname
            or exchange_points is None
            or pack_hourglass_count is None
        )

    def setup(self) -> bool:
        return True

    def cleanup(self):
        pass

    def is_completed(self) -> bool:
        return self._completed

    def check_completion(self) -> Optional[TaskResult]:
        """检查任务完成状态"""
        if self._completed:
            if self._friend_id or self._nickname or self._exchange_points is not None:
                return TaskResult.ok(
                    message=f"获取完成: friend_id={self._friend_id}, nickname={self._nickname}, "
                    f"level={self._level}, exchange_points={self._exchange_points}, "
                    f"pack_hourglass_count={self._pack_hourglass_count}"
                )
            return TaskResult.fail("未能获取账号信息")
        return None

    def handle_page(self, page_name: str, page_info: dict) -> ActionResult:
        """按页面分发到处理函数"""
        handlers = {
            "game_home_main": self._handle_home,
            "profile_page": self._handle_profile,
            "more_menu_modal": self._handle_more_menu_modal,
            "holdings_page": self._handle_holdings_page,
            "holdings_page_scrolled": self._handle_holdings_page,
        }

        handler = handlers.get(page_name)
        if handler:
            return handler(page_info)

        # 兜底：先尝试点主页图标，找不到再用返回
        result = tap_home_icon(self.adb, self.page_detector, wait=3)
        if result and result.success:
            return result
        return navigate_back(
            self.adb,
            self.page_detector,
            page_info.get("ocr_results", []),
        )

    # ============================================================
    # 页面处理方法
    # ============================================================

    def handle_unknown_page(self, page_info) -> ActionResult:
        """处理未知页面"""
        logger.debug("点击屏幕中心兜底")
        return quick_tap(self.adb, y=self.adb.center_y() + 50)

    def _handle_home(self, page_info: dict) -> ActionResult:
        """主页：根据进度决定下一步"""
        ocr = page_info.get("ocr_results", [])

        if not self._is_action_done("profile_fetched"):
            # 第一步：进入个人资料页
            return self._enter_profile(ocr)

        if not self._is_action_done("holdings_fetched"):
            if not self._is_action_done("more_menu_opened"):
                result = tap_template(
                    self.adb,
                    self.page_detector,
                    "icon_bottom_more",
                    wait=1.0,
                )
                if result:
                    self._mark_action_done("more_menu_opened")
                    return result
                return ActionResult.wait(0.8)
            return ActionResult.wait(0.8)

        # 都完成了
        self._update_account()
        self._completed = True
        logger.debug("  -> 任务完成")
        return ActionResult.ok(wait=0.5)

    def _handle_profile(self, page_info: dict) -> ActionResult:
        """个人资料页：提取信息后标记完成"""
        ocr = page_info.get("ocr_results", [])

        # 提取信息
        for item in ocr:
            text = item["text"]
            if not self._friend_id:
                extracted_friend_id = extract_friend_id_from_text(text)
                if extracted_friend_id:
                    self._friend_id = extracted_friend_id
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

        self._mark_action_done("profile_fetched")
        logger.debug("  -> 资料获取完成，返回")
        return navigate_back(self.adb, self.page_detector, ocr)

    def _handle_more_menu_modal(self, page_info: dict) -> ActionResult:
        """更多菜单：精确点击「持有物」进入资源列表。"""
        ocr = page_info.get("ocr_results", [])
        if self._is_action_done("holdings_fetched"):
            return navigate_back(self.adb, self.page_detector, ocr)

        result = tap_text(
            self.adb,
            ocr,
            get_text_patterns("more_menu_holdings"),
            wait=1.5,
            exact=False,
        )
        if result:
            self._mark_action_done("holdings_entered")
            self._holdings_scroll_rounds = 0
            self._holdings_scan_rounds = 0
            logger.info("  -> 点击持有物")
            return result
        return ActionResult.wait(0.8)

    def _handle_holdings_page(self, page_info: dict) -> ActionResult:
        """持有物页面：提取开包沙漏和闪亮沙子。"""
        ocr = page_info.get("ocr_results", [])
        exchange_points, pack_hourglass_count = self._extract_holdings_values(ocr)
        if exchange_points is not None:
            self._exchange_points = exchange_points
            logger.debug("  -> 识别閃亮沙子: %s", exchange_points)
        if pack_hourglass_count is not None:
            self._pack_hourglass_count = pack_hourglass_count
            logger.debug("  -> 识别開包沙漏: %s", pack_hourglass_count)

        if self._exchange_points is not None and self._pack_hourglass_count is not None:
            self._mark_action_done("holdings_fetched")
            logger.info(
                "  -> 获取持有物完成: exchange_points=%s, pack_hourglass_count=%s",
                self._exchange_points,
                self._pack_hourglass_count,
            )
            return navigate_back(self.adb, self.page_detector, ocr)

        self._holdings_scan_rounds += 1
        if self._holdings_scan_rounds <= MIN_HOLDINGS_SCAN_ROUNDS_BEFORE_SCROLL:
            logger.debug(
                "  -> 持有物页面先扫描后滑动 (%s/%s)",
                self._holdings_scan_rounds,
                MIN_HOLDINGS_SCAN_ROUNDS_BEFORE_SCROLL,
            )
            return ActionResult.wait(0.8)

        if self._holdings_scroll_rounds >= MAX_HOLDINGS_SCROLL_ROUNDS:
            logger.warning("  -> 持有物页面滑动到上限，仍未提取到完整资源")
            self._mark_action_done("holdings_fetched")
            return navigate_back(self.adb, self.page_detector, ocr)

        self._holdings_scroll_rounds += 1
        start, end = scroll_points(
            self.adb,
            base_distance_y=BASE_HOLDINGS_SCROLL_DISTANCE_Y,
            direction="up",
        )
        swipe(self.adb, start, end, wait=HOLDINGS_SCROLL_SETTLE_WAIT)
        return ActionResult.ok(wait=HOLDINGS_SCROLL_SETTLE_WAIT)

    def _enter_profile(self, ocr: list) -> ActionResult:
        """点击头像进入个人资料"""
        lv_pos = self._find_lv_position(ocr)
        if lv_pos:
            logger.info("  -> 点击头像区域")
            return tap_above_point(
                self.adb, lv_pos, BASE_AVATAR_OFFSET_Y, MIN_TAP_Y, wait=5.0
            )
        logger.debug("  -> 未找到 Lv.，点击中上方")
        return tap_top_center(self.adb, BASE_FALLBACK_TAP_Y, wait=2.0)

    def _find_lv_position(self, ocr: list) -> Optional[tuple]:
        """查找 Lv. 位置"""
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

        exclude = get_text_patterns("profile_exclude")
        search_range = self.adb.scaled_y(300)
        candidates = []

        for item in ocr:
            text, box = item["text"], item["box"]
            y = (box[1] + box[3]) // 2
            if lv_y < y < lv_y + search_range:
                if any(p in text for p in exclude):
                    continue
                if (
                    "/" in text
                    and text.replace(",", "")
                    .replace("/", "")
                    .replace(".", "")
                    .isdigit()
                ):
                    continue
                if text.replace(",", "").replace(".", "").isdigit():
                    continue
                if len(text) >= 2:
                    candidates.append((text, y))

        if candidates:
            candidates.sort(key=lambda x: x[1])
            return candidates[0][0]
        return None

    def _extract_holdings_values(
        self, ocr: list
    ) -> tuple[Optional[int], Optional[int]]:
        """从持有物页面提取闪亮沙子与开包沙漏数量。"""
        flash_patterns = get_text_patterns("holdings_flash_sand")
        hourglass_patterns = get_text_patterns("holdings_pack_hourglass")
        label_texts: list[str] = []
        number_texts: list[str] = []

        for item in ocr:
            text = str(item.get("text", ""))
            normalized = "".join(text.split())
            if any(
                "".join(p.split()) in normalized
                for p in flash_patterns + hourglass_patterns
            ):
                label_texts.append(text)
            if self._parse_numeric_text(text) is not None:
                number_texts.append(text)

        logger.debug(
            "  -> 持有物OCR标签=%s, 数字=%s",
            label_texts,
            number_texts,
        )

        exchange_points = self._extract_value_near_label(
            ocr,
            flash_patterns,
        )
        pack_hourglass_count = self._extract_value_near_label(
            ocr,
            hourglass_patterns,
        )

        logger.debug(
            "  -> 持有物识别结果: 閃亮沙子=%s, 開包沙漏=%s",
            exchange_points,
            pack_hourglass_count,
        )
        return exchange_points, pack_hourglass_count

    def _extract_value_near_label(
        self,
        ocr: list,
        label_patterns: list[str],
    ) -> Optional[int]:
        """按标签与数字的Y轴距离最近原则提取数值。"""
        normalized_patterns = {"".join(pattern.split()) for pattern in label_patterns}
        label_center_ys: list[int] = []
        numbers: list[tuple[int, tuple[int, int, int, int]]] = []

        for item in ocr:
            box = item.get("box")
            if not box:
                continue
            text = "".join(str(item.get("text", "")).split())
            if any(pattern in text for pattern in normalized_patterns):
                label_center_ys.append((box[1] + box[3]) // 2)
                continue

            value = self._parse_numeric_text(text)
            if value is not None:
                numbers.append((value, tuple(box)))

        if not label_center_ys or not numbers:
            return None

        best_value: Optional[int] = None
        best_dy: Optional[int] = None
        for label_y in label_center_ys:
            for value, number_box in numbers:
                number_y = (number_box[1] + number_box[3]) // 2
                dy = abs(number_y - label_y)
                if best_dy is None or dy < best_dy:
                    best_dy = dy
                    best_value = value

        return best_value

    @staticmethod
    def _parse_numeric_text(text: str) -> Optional[int]:
        """解析 OCR 中的数字文本。"""
        normalized = text.replace(",", "").replace(" ", "")
        if not normalized.isdecimal():
            return None
        value = int(normalized)
        if 0 <= value <= 999999:
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
        if changed:
            AccountRepository().update(self.account)

        if self.account.id is None:
            return

        stat_repo = AccountStatRepository()
        existing_stat = stat_repo.get_by_account_id(int(self.account.id))
        exchange_points = (
            self._exchange_points
            if self._exchange_points is not None
            else (existing_stat.exchange_points if existing_stat else None)
        )
        pack_hourglass_count = (
            self._pack_hourglass_count
            if self._pack_hourglass_count is not None
            else (existing_stat.pack_hourglass_count if existing_stat else None)
        )

        stat_changed = False
        if existing_stat is None:
            stat_changed = (
                exchange_points is not None or pack_hourglass_count is not None
            )
        else:
            stat_changed = (
                existing_stat.exchange_points != exchange_points
                or existing_stat.pack_hourglass_count != pack_hourglass_count
            )

        if stat_changed:
            stat_repo.upsert(
                account_id=int(self.account.id),
                exchange_points=exchange_points,
                pack_hourglass_count=pack_hourglass_count,
            )

        if changed or stat_changed:
            logger.info(
                f"已更新账号: friend_id={self.account.friend_id}, nickname={self.account.nickname}, "
                f"level={self.account.level}, exchange_points={exchange_points}, "
                f"pack_hourglass_count={pack_hourglass_count}"
            )
