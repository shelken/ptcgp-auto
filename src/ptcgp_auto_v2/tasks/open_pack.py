# -*- coding: utf-8 -*-
"""
开包任务模块

采用字典映射处理页面，使用 action_cache 管理页面内操作状态。
流程：主页检测免费包 → 选择系列 → 选择子包 → 开包 → 登录图鉴 → 回到主页检查
"""

import logging
import time
from typing import TYPE_CHECKING, Any, Optional

from ptcgp_auto_v2.config.constants import PACK_TEMPLATE_THRESHOLD
from ptcgp_auto_v2.config.settings import get_settings
from ptcgp_auto_v2.core.task_base import (
    ActionResult,
    ResetType,
    Task,
    TaskRegistry,
    TaskResult,
)
from ptcgp_auto_v2.locales import get_text_patterns, get_config_value
from ptcgp_auto_v2.utils.card_naming import normalize_name_str
from ptcgp_auto_v2.utils.gesture import (
    tap_center,
    navigate_back,
    swipe,
    long_press_text,
    tap_home_icon,
    click_close,
    tap_bottom_close,
    tap_box,
    tap_continue,
    swipe_pack_coords,
    swipe_card_coords,
    tap_template_or_text,
    tap_template_with_scale,
    scroll_until_template,
    quick_tap,
)

if TYPE_CHECKING:
    from ptcgp_auto_v2.db.repositories import (
        AccountPackConfigRepository,
        PackRecordRepository,
        CardRepository,
        AccountPackPointRepository,
    )

logger = logging.getLogger(__name__)

# 延迟导入 OpenPackTask（避免循环导入）
_open_pack_task = None


# ============================================================
# 常量定义（基于 1080x1920 基准分辨率的像素值）
# ============================================================

# 沙漏弹窗关闭点击位置（屏幕底部区域）
BASE_POPUP_CLOSE_TAP_Y = 1820  # 1920 * 0.95

# 开包滑动时长 (ms)
SWIPE_DURATION_OPEN = 500
# 登录图鉴滑动时长 (ms)
SWIPE_DURATION_REGISTER = 100

# 主页无免费包检查次数阈值
HOME_CHECK_THRESHOLD = 3

# 跳过原因常量
SKIP_REASON_NO_ACCOUNT_ID = "账号 ID 为空"
SKIP_REASON_NO_PACK_CONFIG = "未配置开包目标"


# ============================================================
# 页面识别规则
# ============================================================


def _build_pack_pages() -> list[dict]:
    """构建开包任务页面规则"""
    return [
        {
            "name": "pack_series_select",
            "identifiers": get_text_patterns("pack_series_select"),
            "priority": 99,
            "exact_match": True,
        },
        {
            "name": "pack_list",
            "identifiers": get_text_patterns("pack_list"),
            "match_all": True,
            "exclude_identifiers": get_text_patterns("pack_list_exclude"),
            "priority": 99,
        },
        {
            "name": "pack_opening_swipe",
            "identifiers": get_text_patterns("pack_opening_swipe"),
            "priority": 99,
        },
        {
            "name": "pack_opening_select",
            "identifiers": get_text_patterns("pack_opening_select"),
            "priority": 99,
        },
        {
            "name": "pack_opening_card",
            "identifiers": get_text_patterns("long_press"),
            "priority": 99,
        },
        {
            "name": "pack_opening_result",
            "identifiers": get_text_patterns("pack_opening_result"),
            "priority": 99,
        },
        {
            "name": "pack_card_register",
            "identifiers": get_text_patterns("pack_card_register"),
            "priority": 99,
        },
        {
            "name": "pack_detail",
            "identifiers": get_text_patterns("open_pack"),
            "exclude_identifiers": get_text_patterns("open_pack_exclude"),
            "priority": 99,
            "exact_match": True,
        },
        {
            "name": "pack_hourglass_popup",
            "identifiers": get_text_patterns("pack_hourglass_popup"),
            "priority": 99,
        },
        {
            "name": "game_home_main",
            "match_all": True,
            "identifiers": get_text_patterns("game_home_main"),
            "priority": 99,
        },
        {
            "name": "home_icon",
            "templates": ["icon_home"],
            "priority": 99,
        },
    ]


@TaskRegistry.register("open_pack")
class OpenPackTask(Task):
    """
    开包任务

    流程：主页检测免费包 → 进入开包流程 → 选择系列 → 选择子包 → 开封 → 滑动开包 → 识别结果 → 返回主页检查
    """

    task_type = "open_pack"
    reset_type = ResetType.DAILY
    max_iterations = 100
    max_unknown_pages = 15
    pages = _build_pack_pages()

    def __init__(self, adb, recognizer, page_detector):
        super().__init__(adb, recognizer, page_detector)

        # 初始化卡牌识别器
        from ptcgp_auto_v2.infra.card_recognizer import CardRecognizer

        _, template_matcher = recognizer
        self.card_recognizer = CardRecognizer(adb, template_matcher)

        # 页面内操作缓存（用于记录当前页面已完成操作）
        self._action_cache: dict[str, bool] = {}

        # 任务状态
        self._home_check_count = 0  # 主页无免费包检查次数
        self._packs_opened_count = 0  # 本次任务已开包数量
        self._result_recognized = False  # 本次开包是否已识别结果
        self._skip_reason: Optional[str] = None  # 跳过原因
        self._completed = False  # 任务完成标志
        self._skipped = False  # 任务跳过标志

        # 目标卡包配置
        self.target_pack: dict[str, str] | None = None
        self._boosters_list: list[str] = []

        # 数据仓储（延迟加载）
        self._pack_config_repo: "AccountPackConfigRepository | None" = None
        self._pack_record_repo: "PackRecordRepository | None" = None
        self._card_repo: "CardRepository | None" = None
        self._pack_point_repo: "AccountPackPointRepository | None" = None

    def _is_action_done(self, key: str) -> bool:
        """检查操作是否已完成"""
        return self._action_cache.get(key, False)

    def _mark_action_done(self, key: str):
        """标记操作已完成"""
        self._action_cache[key] = True

    def _reset_action_cache(self):
        """重置操作缓存（进入新页面时调用）"""
        self._action_cache.clear()

    def on_start(self):
        """任务开始前的初始化"""
        from ptcgp_auto_v2.db.repositories import (
            AccountPackConfigRepository,
            PackRecordRepository,
            CardRepository,
            AccountPackPointRepository,
        )

        self._pack_config_repo = AccountPackConfigRepository()
        self._pack_record_repo = PackRecordRepository()
        self._card_repo = CardRepository()
        self._pack_point_repo = AccountPackPointRepository()

        self._action_cache.clear()
        self._home_check_count = 0
        self._packs_opened_count = 0
        self._completed = False
        self._skipped = False

        # 检查账号 ID
        if self.account.id is None:
            logger.error(f"账号 {self.account.display_name} ID 为空")
            self._skipped = True
            self._skip_reason = SKIP_REASON_NO_ACCOUNT_ID
            return

        # 加载开包配置
        config = self._pack_config_repo.get_by_account_and_type(
            self.account.id, "daily"
        )

        if not config:
            # 未配置时，自动选择最新发布的系列
            logger.info(
                f"账号 {self.account.display_name} 未配置开包目标，尝试选择最新系列"
            )
            result = self._card_repo.get_latest_set_with_pack()
            if result:
                card_set, pack = result
                self.target_pack = {
                    "pack_code": card_set.code,
                    "booster_name": pack.name,
                }
                logger.info(f"自动选择最新卡包: {card_set.code}/{pack.name}")
            else:
                logger.info(
                    f"账号 {self.account.display_name} 无法找到可用的开包目标，任务跳过"
                )
                self._skipped = True
                self._skip_reason = SKIP_REASON_NO_PACK_CONFIG
                return
        else:
            self.target_pack = {
                "pack_code": config.pack_code,
                "booster_name": config.booster_name,
            }
            logger.info(f"目标卡包: {config.pack_code}/{config.booster_name}")

        # 准备图片资源
        self._prepare_image_resources()

        # 加载子包列表
        pack_code = self.target_pack.get("pack_code") if self.target_pack else None
        self._boosters_list = self._load_boosters_list(pack_code) if pack_code else []

    def _prepare_image_resources(self):
        """准备图片资源（按需加载）"""
        pack_code = self.target_pack.get("pack_code") if self.target_pack else None
        booster_name = (
            self.target_pack.get("booster_name") if self.target_pack else None
        )
        if not pack_code or not booster_name:
            return

        try:
            from ptcgp_auto_v2.utils.pack_image_manager import PackImageManager

            manager = PackImageManager()
            # 确保目标卡包图片已就绪
            if manager.ensure_pack_ready(booster_name):
                # 加载该卡包模板
                pack_path = manager.get_pack_path(booster_name)
                if self.recognizer:
                    _, template_matcher = self.recognizer
                    # 使用模板相对路径（packs_auto/xxx）
                    template_name = manager.get_template_name(booster_name)
                    template_matcher.load_additional_templates(f"packs_auto")
                    logger.debug(f"已加载卡包模板: {template_name}")
            else:
                logger.error(f"准备卡包图片资源失败: {booster_name}")
        except Exception as e:
            logger.error(f"准备卡包图片资源失败: {e}")

    def is_completed(self) -> bool:
        """判断任务是否已完成"""
        return self._completed or self._skipped

    def was_skipped(self) -> bool:
        """判断任务是否被跳过"""
        return self._skipped

    def handle_page(self, page_name: str, page_info: dict) -> ActionResult:
        """处理识别到的页面"""
        logger.debug(f"处理页面: {page_name}")

        # 页面处理器映射
        handlers = {
            "game_home_main": self._handle_home,
            "home_icon": self._handle_home_icon,
            "pack_series_select": self._handle_pack_series_select,
            "pack_list": self._handle_pack_list,
            "pack_detail": self._handle_pack_detail,
            "pack_hourglass_popup": self._handle_hourglass_popup,
            "pack_opening_swipe": self._handle_opening_swipe,
            "pack_opening_card": self._handle_opening_card,
            "pack_card_register": self._handle_card_register,
            "pack_opening_result": self._handle_pack_opening_result,
            "pack_opening_select": self._handle_pack_opening_select,
        }

        handler = handlers.get(page_name)
        if handler:
            return handler(page_info)

        logger.warning(f"未处理的页面: {page_name}")
        return ActionResult.ok(wait=1.0)

    def handle_unknown_page(self, page_info) -> ActionResult:
        """处理未知页面"""
        logger.debug("未知页面，点击屏幕中心兜底")
        return quick_tap(self.adb, wait=0.5)

    def on_complete(self, result: TaskResult):
        """任务完成后的处理"""
        logger.info(
            f"任务完成，已开包: {self._packs_opened_count}, "
            f"结果: {'跳过' if result.skipped else ('成功' if result.success else '失败')}"
        )

        if result.success and not result.skipped and self._packs_opened_count > 0:
            logger.info(f"本次共开 {self._packs_opened_count} 包")

        # 清理卡包模板资源
        if self.recognizer:
            try:
                _, template_matcher = self.recognizer
                template_matcher.unload_pack_templates()
            except Exception as e:
                logger.warning(f"卸载卡包模板失败: {e}")

    # ============================================================
    # 页面处理方法
    # ============================================================

    def _handle_home(self, page_info: dict) -> ActionResult:
        """处理主页：核心决策点，检查免费包"""
        self._reset_action_cache()
        screenshot, ocr_results = self.page_detector.get_last_page_context()

        if not screenshot:
            logger.warning("  -> 无法获取截图")
            return ActionResult.ok(wait=1.0)

        # 检查是否有免费包图标
        free_pack_box = self.page_detector.find_template_with_scale(
            "icon_free_pack_available", screenshot=screenshot
        )

        if free_pack_box:
            # 有免费包，重置计数，进入开包流程
            logger.debug("  -> 检测到免费包，进入开包流程")
            self._home_check_count = 0

            # 点击开包入口图标
            pack_open_box = self.page_detector.find_template_with_scale(
                "icon_pack_open", screenshot=screenshot
            )
            if pack_open_box:
                return tap_box(self.adb, pack_open_box.box, wait=1.0)
            logger.warning("  -> 未找到开包图标")
            return ActionResult.ok(wait=1.0)

        # 无免费包，累计计数
        self._home_check_count += 1
        logger.debug(
            f"  -> 未检测到免费包 ({self._home_check_count}/{HOME_CHECK_THRESHOLD})"
        )

        if self._home_check_count >= HOME_CHECK_THRESHOLD:
            logger.debug("  -> 确认无免费包，任务完成")
            self._completed = True

        return ActionResult.ok(wait=1.0)

    def _handle_home_icon(self, page_info: dict) -> ActionResult:
        """点击主页图标回到游戏主页"""
        logger.debug("  -> 点击主页图标回到游戏主页")
        return tap_home_icon(self.adb, self.page_detector, wait=1.0)

    def _handle_pack_series_select(self, page_info: dict) -> ActionResult:
        """选择扩充包系列"""
        screenshot, ocr_results = self.page_detector.get_last_page_context()

        if not screenshot:
            return ActionResult.fail("截图失败")

        settings = get_settings()
        template_name = self._get_target_template_name()
        if not template_name:
            return ActionResult.fail("未配置目标卡包模板")

        # 1. 模板匹配查找目标扩充包
        result = tap_template_with_scale(
            self.page_detector,
            template_name,
            scale=settings.scale_pack_series_select,
            wait=1.0,
        )
        if result:
            logger.debug("  -> 找到目标扩充包，点击进入")
            self._reset_action_cache()
            return result

        # 2. 尝试切换到目标系列
        target_series = self._get_target_series()
        if target_series and not self._is_action_done("series_clicked"):
            series_patterns = get_config_value("series")
            if isinstance(series_patterns, dict) and target_series in series_patterns:
                patterns = series_patterns[target_series]
                result = tap_template_or_text(
                    self.adb, self.page_detector, ocr_results, None, patterns, wait=1.0
                )
                if result:
                    self._mark_action_done("series_clicked")
                    logger.debug(f"  -> 点击切换到 {target_series} 系列")
                    return result

        # 3. 上滑查找
        max_attempts = settings.max_scroll_attempts
        result = scroll_until_template(
            self.page_detector,
            template_name,
            scale=settings.scale_pack_series_select,
            max_attempts=max_attempts,
            swipe_ratio=0.23,  # 旧值: 0.21
            wait=1.2,
        )
        if result:
            return result

        # 未找到，返回上一页
        return navigate_back(
            self.adb, self.page_detector, ocr_results, get_text_patterns("back_button")
        )

    def _handle_pack_list(self, page_info: dict) -> ActionResult:
        """选择子包"""
        screenshot, ocr_results = self.page_detector.get_last_page_context()

        if not screenshot:
            return ActionResult.fail("截图失败")

        settings = get_settings()
        template_name = self._get_target_template_name()
        if not template_name:
            return ActionResult.fail("未配置目标卡包模板")

        # 直接判断当前是否匹配目标包模板
        match = self.page_detector.find_template_with_scale(
            template_name,
            scale=settings.scale_pack_list,
            threshold=PACK_TEMPLATE_THRESHOLD,
        )

        # 如果不匹配，尝试切换子包
        if not match:
            from ptcgp_auto_v2.utils.gesture import tap_right_side

            for attempt in range(len(self._boosters_list)):
                logger.info(f"  -> 第 {attempt + 1} 次切换子包")
                tap_right_side(self.page_detector.adb, wait=1.0)
                screenshot, ocr_results = self.page_detector.capture()
                if not screenshot:
                    continue
                match = self.page_detector.find_template_with_scale(
                    template_name,
                    scale=settings.scale_pack_list,
                    screenshot=screenshot,
                    threshold=PACK_TEMPLATE_THRESHOLD,
                )
                if match:
                    break

            if not match:
                logger.warning("  -> 循环切换子包未找到目标，返回上一页")
                return navigate_back(
                    self.adb,
                    self.page_detector,
                    ocr_results,
                    get_text_patterns("back_button"),
                )

        # 匹配成功，提取点数
        self._extract_pack_points(ocr_results)

        # 点击进入详情
        logger.debug("  -> 找到目标子包，点击进入详情")
        self._reset_action_cache()
        return tap_box(self.page_detector.adb, match.box, wait=1.0)

    def _extract_pack_points(self, ocr_results: list[dict]) -> None:
        """从 OCR 结果中提取并保存开包点数"""
        if not (self.account.id and self.target_pack and self._pack_point_repo):
            return

        try:
            import re

            for item in ocr_results:
                text = item.get("text", "")
                match = re.search(r"([\d,]+)\s*pt", text, re.IGNORECASE)
                if match:
                    points_str = match.group(1).replace(",", "")
                    points = int(points_str)
                    series = self.target_pack.get("pack_code", "Unknown")
                    self._pack_point_repo.upsert_points(self.account.id, series, points)
                    logger.debug(f"  -> 更新开包点数: {series} = {points}pt")
                    break
        except Exception as e:
            logger.warning(f"  -> 提取开包点数失败: {e}")

    def _handle_pack_detail(self, page_info: dict) -> ActionResult:
        """点击开包按钮"""
        screenshot, ocr_results = self.page_detector.get_last_page_context()

        if not screenshot:
            return ActionResult.fail("截图失败")

        # 检查当前卡包是否是目标卡包
        if self.target_pack:
            settings = get_settings()
            template_name = self._get_target_template_name()
            if not template_name:
                return ActionResult.fail("未配置目标卡包模板")

            match = self.page_detector.find_template_with_scale(
                template_name,
                scale=settings.scale_pack_detail,
                screenshot=screenshot,
                threshold=PACK_TEMPLATE_THRESHOLD,
            )
            if not match:
                logger.info(f"  -> 当前卡包不是目标卡包 ({template_name})，返回")
                return navigate_back(
                    self.adb,
                    self.page_detector,
                    ocr_results,
                    get_text_patterns("back_button"),
                )

        # 检查是否是付费包
        paid_patterns = get_text_patterns("open_pack_1")
        if paid_patterns and any(
            pattern in item["text"] for pattern in paid_patterns for item in ocr_results
        ):
            logger.info("  -> 检测到付费包，返回上一页")
            return navigate_back(
                self.adb,
                self.page_detector,
                ocr_results,
                get_text_patterns("back_button"),
            )

        # 点击"開封"按钮
        open_pack_patterns = get_text_patterns("open_pack")
        result = tap_template_or_text(
            self.adb,
            self.page_detector,
            ocr_results,
            None,
            open_pack_patterns,
            wait=1.0,
        )
        if result:
            logger.info("  -> 点击开封按钮，进入开包流程")
            return result

        logger.warning("  -> 未找到开包按钮")
        return ActionResult.ok(wait=1.0)

    def _handle_hourglass_popup(self, page_info: dict) -> ActionResult:
        """处理沙漏弹窗"""
        ocr_results = page_info.get("ocr_results", [])
        close_patterns = get_text_patterns("close_button")

        result = click_close(self.adb, self.page_detector, ocr_results, close_patterns)
        if result:
            logger.debug("  -> 点击关闭弹窗")
            return result

        logger.debug("  -> 点击屏幕底部关闭弹窗")
        return tap_bottom_close(self.adb, BASE_POPUP_CLOSE_TAP_Y, wait=1.0)

    def _handle_opening_swipe(self, page_info: dict) -> ActionResult:
        """滑动开包"""
        logger.debug("  -> 从左往右滑动开包")
        self._packs_opened_count += 1
        self._result_recognized = False
        start, end = swipe_pack_coords(self.adb)
        return swipe(self.adb, start, end, duration=SWIPE_DURATION_OPEN)

    def _handle_opening_card(self, page_info: dict) -> ActionResult:
        """长按跳过卡牌展示"""
        ocr_results = page_info.get("ocr_results", [])
        long_press_patterns = get_text_patterns("long_press")

        wait = 3.0
        result = long_press_text(self.adb, ocr_results, long_press_patterns, wait=wait)
        if result:
            logger.debug("  -> 长按文字跳过卡牌展示")
            return result

        self._home_check_count = 0
        return ActionResult.ok(wait=wait)

    def _handle_pack_opening_select(self, page_info: dict) -> ActionResult:
        """点击选择要开的扩充包"""
        logger.debug("  -> 点击屏幕中心选择扩充包")
        return tap_center(self.adb, wait=1.0)

    def _handle_card_register(self, page_info: dict) -> ActionResult:
        """向上滑动卡牌登录图鉴"""
        logger.debug(f"  -> 向上滑动卡牌（已开 {self._packs_opened_count} 包）")
        start, end = swipe_card_coords(self.adb)
        return swipe(self.adb, start, end, duration=SWIPE_DURATION_REGISTER)

    def _handle_pack_opening_result(self, page_info: dict) -> ActionResult:
        """处理开包结果页：识别卡牌并点击继续"""
        if not self._result_recognized:
            self._recognize_cards()

        logger.debug("  -> 点击继续")
        return tap_continue(self.adb, page_info.get("ocr_results", []), wait=1.5)

    def _recognize_cards(self):
        """识别卡牌并保存记录"""
        max_retries = 3
        for attempt in range(max_retries):
            try:
                cards = self.card_recognizer.scan_pack_result()
                if cards:
                    if self._packs_opened_count == 0:
                        self._packs_opened_count = 1

                    card_names = [f"{c.name}({c.confidence:.2f})" for c in cards]
                    logger.debug(f"====== 识别到 {len(cards)} 张卡牌 ======")

                    set_code = (
                        self.target_pack.get("pack_code", "Unknown")
                        if self.target_pack
                        else "Unknown"
                    )
                    current_batch_cards = []

                    for i, c in enumerate(cards):
                        logger.debug(f"  - {c.name} (Conf: {c.confidence:.2f})")
                        card_obj = (
                            self._card_repo.get_card_by_template_name(set_code, c.name)
                            if self._card_repo
                            else None
                        )

                        card_data = {
                            "card_name": card_obj.name if card_obj else c.name,
                            "rarity": card_obj.rarity if card_obj else "Unknown",
                            "card_id": card_obj.id if card_obj else None,
                            "is_new": False,
                            "position": i + 1,
                            "confidence": float(c.confidence),
                        }
                        current_batch_cards.append(card_data)

                    # 即时保存数据库
                    if self._pack_record_repo and self.account.id:
                        try:
                            pack_type = "daily_free"
                            pack_code = (
                                self.target_pack.get("pack_code")
                                if self.target_pack
                                else None
                            )
                            pack_name = (
                                self.target_pack.get("booster_name")
                                if self.target_pack
                                else None
                            )

                            self._pack_record_repo.create_for_account(
                                self.account.id,
                                pack_type=pack_type,
                                pack_code=pack_code,
                                pack_name=pack_name,
                                cards=current_batch_cards,
                            )
                            card_names = [
                                f"{c['card_name']}({c['rarity']})"
                                for c in current_batch_cards
                            ]
                            logger.info(
                                f"已保存开包记录: {pack_code}/{pack_name} ({len(current_batch_cards)} 张): {', '.join(card_names)}"
                            )
                        except Exception as e:
                            logger.error(f"保存开包记录失败: {e}")

                    logger.debug("==================================")
                    self._result_recognized = True
                    break
                else:
                    if attempt < max_retries - 1:
                        logger.debug(
                            f"未识别到卡牌，等待重试 ({attempt + 1}/{max_retries})"
                        )
                        time.sleep(2.0)
                    else:
                        logger.warning(f"卡牌识别连续失败 {max_retries} 次，跳过识别")
                        self._result_recognized = True

            except RuntimeError as e:
                logger.error(f"识别卡牌失败: {e}")
                if attempt >= max_retries - 1:
                    self._result_recognized = True

    def _load_boosters_list(self, pack_code: str) -> list[str]:
        """从 packs.json 加载子包列表"""
        from ptcgp_auto_v2.utils.packs import get_boosters

        boosters = get_boosters(pack_code)
        logger.debug(f"系列 {pack_code} 有 {len(boosters)} 个子包: {boosters}")
        return boosters

    def _get_target_series(self) -> Optional[str]:
        """根据 pack_code 获取目标系列（A/B）"""
        if not self.target_pack:
            return None
        pack_code = self.target_pack["pack_code"]
        return pack_code[0].upper() if pack_code else None

    def _get_target_template_name(self) -> Optional[str]:
        """获取目标卡包的模板名称"""
        if not self.target_pack:
            return None
        booster_name = normalize_name_str(self.target_pack["booster_name"])
        return f"packs_auto/{booster_name}"
