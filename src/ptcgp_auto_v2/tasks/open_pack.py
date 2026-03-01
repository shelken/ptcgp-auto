# -*- coding: utf-8 -*-
"""
开包任务模块

采用字典映射处理页面，使用 action_cache 管理页面内操作状态。
流程：主页检测免费包 → 选择系列 → 选择子包 → 开包 → 登录图鉴 → 回到主页检查

继承 PackOpeningTaskBase，复用统一开包流程，保留主页与选包业务入口。
"""

import logging
from typing import TYPE_CHECKING, Optional

from ptcgp_auto_v2.config.constants import (
    PACK_AUTO_EXCLUDE_SET_CODES,
    PACK_SERIES_CODES,
    SWIPE_STEPS_SCROLL,
)
from ptcgp_auto_v2.config.settings import get_settings
from ptcgp_auto_v2.core.task_base import (
    ActionResult,
    ResetType,
    TaskRegistry,
    TaskResult,
)
from ptcgp_auto_v2.locales import get_config_value, get_text_patterns
from ptcgp_auto_v2.tasks.pack_opening_task_base import (
    PackOpeningTaskBase,
    build_pack_opening_pages,
)
from ptcgp_auto_v2.utils.gesture import (
    click_close,
    navigate_back,
    quick_tap,
    scroll_until_template,
    tap_bottom_close,
    tap_box,
    tap_right_side,
    tap_template_or_text,
    tap_template_with_scale,
)
from ptcgp_auto_v2.utils.pack_auto_selector import select_pack_for_account

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)


# ============================================================
# 常量定义（基于 1080x1920 基准分辨率的像素值）
# ============================================================

# 沙漏弹窗关闭点击位置（屏幕底部区域）
BASE_POPUP_CLOSE_TAP_Y = 1820  # 1920 * 0.95

# 系列选择页面滚动步进
BASE_PACK_SERIES_SCROLL_DISTANCE_Y = 307  # 1920 * 0.16


# 主页无免费包检查次数阈值
HOME_CHECK_THRESHOLD = 3


# ============================================================
# 页面识别规则
# ============================================================


def _build_open_pack_pages() -> list[dict]:
    """构建开包任务特定页面规则（与通用开包页面合并）"""
    task_specific_pages = [
        # 選擇擴充組
        {
            "name": "pack_series_select",
            "identifiers": get_text_patterns("pack_series_select"),
            "priority": 99,
            "exact_match": True,
        },
        # 提供比例 / 其他擴充包
        {
            "name": "pack_list",
            "identifiers": get_text_patterns("pack_list"),
            "match_all": True,
            "exclude_identifiers": get_text_patterns("pack_list_exclude"),
            "priority": 99,
        },
        # 開封
        {
            "name": "pack_detail",
            "identifiers": get_text_patterns("open_pack"),
            "exclude_identifiers": get_text_patterns("open_pack_exclude"),
            "priority": 99,
            "exact_match": True,
        },
        # 要使用道具縮短等待時間
        {
            "name": "pack_hourglass_popup",
            "identifiers": get_text_patterns("pack_hourglass_popup"),
            "priority": 99,
        },
        # 商店 / 得卡挑戰
        {
            "name": "game_home_main",
            "match_all": True,
            "identifiers": get_text_patterns("game_home_main"),
            "priority": 99,
        },
    ]
    return task_specific_pages + build_pack_opening_pages()


@TaskRegistry.register("open_pack")
class OpenPackTask(PackOpeningTaskBase):
    """
    开包任务

    流程：主页检测免费包 → 进入开包流程 → 选择系列 → 选择子包 → 开封 → 滑动开包 → 识别结果 → 返回主页检查

    继承 PackOpeningTaskBase，复用开包页面处理、识别和记录保存。
    """

    task_type = "open_pack"
    reset_type = ResetType.DAILY
    max_iterations = 100
    max_unknown_pages = 15
    pages = _build_open_pack_pages()

    def __init__(self, adb, recognizer, page_detector):
        super().__init__(adb, recognizer, page_detector)

        # 任务状态
        self._home_check_count = 0  # 主页无免费包检查次数
        self._completed = False  # 任务完成标志
        self._skipped = False  # 任务跳过标志
        self._fail_reason: Optional[str] = None  # 失败原因

        # 目标卡包配置
        self._target_pack: dict[str, str] | None = None

        # 数据仓储（基类已初始化，此处仅用于类型提示）
        self._pack_config_repo = None

    # ============================================================
    # 扩展点实现（PackOpeningTaskBase 要求）
    # ============================================================

    def get_pack_record_type(self) -> str:
        """返回 pack 记录类型：每日免费包"""
        return "daily_free"

    def get_rare_card_notify_message(self) -> str:
        """返回稀有卡通知消息：每日开包"""
        return "开包获得稀有卡牌"

    def get_target_pack_context(self) -> dict[str, str] | None:
        """获取目标卡包上下文"""
        return self._target_pack

    def should_prepare_pack_resources(self) -> bool:
        """open_pack 需要准备卡包图片资源"""
        return True

    # ============================================================
    # 任务生命周期
    # ============================================================

    def on_start(self):
        """任务开始前的初始化"""
        from ptcgp_auto_v2.db.repositories import AccountPackConfigRepository

        self._init_repositories()
        self._pack_config_repo = AccountPackConfigRepository()

        self._action_cache.clear()
        self._home_check_count = 0
        self._packs_opened_count = 0
        self._completed = False
        self._skipped = False
        self._failed = False  # 任务失败标志
        self._result_recognized = False

        # 检查账号 ID
        if self.account.id is None:
            logger.error(f"账号 {self.account.display_name} ID 为空")
            self._skipped = True
            return

        # 加载开包配置
        config = self._pack_config_repo.get_by_account_and_type(
            self.account.id, "daily"
        )

        if not config:
            # 未配置时，自动选择卡包策略
            logger.info(
                f"账号 {self.account.display_name} 未配置开包目标，尝试自动选择"
            )
            settings = get_settings()
            selected = select_pack_for_account(
                account=self.account,
                strategy=settings.pack_auto_strategy,
                card_repo=self._card_repo,
                record_repo=self._pack_record_repo,
                exclude_set_codes=PACK_AUTO_EXCLUDE_SET_CODES,
            )
            if not selected:
                logger.info(
                    f"账号 {self.account.display_name} 无法找到可用的开包目标，任务跳过"
                )
                self._skipped = True
                return

            self._target_pack = {
                "pack_code": selected["pack_code"],
                "booster_name": selected["booster_name"],
            }
            logger.info(
                "自动选择卡包: %s/%s (策略=%s, 候选=%s)",
                selected["pack_code"],
                selected["booster_name"],
                selected.get("strategy"),
                selected.get("candidate_count"),
            )
        else:
            self._target_pack = {
                "pack_code": config.pack_code,
                "booster_name": config.booster_name,
            }
            logger.info(f"目标卡包: {config.pack_code}/{config.booster_name}")

        # 准备图片资源
        if self.should_prepare_pack_resources():
            if not self._prepare_image_resources():
                logger.error("准备卡包图片资源失败")
                self._failed = True
                self._fail_reason = "准备卡包图片资源失败"
                return

        # 预加载目标系列 Hash
        self._preload_target_series_hash()

    def _prepare_image_resources(self) -> bool:
        """准备图片资源（失败将直接结束任务）"""
        pack_code = self._target_pack.get("pack_code") if self._target_pack else None
        booster_name = (
            self._target_pack.get("booster_name") if self._target_pack else None
        )
        if not pack_code or not booster_name:
            logger.error(
                f"准备卡包图片资源失败: pack_code={pack_code}, booster_name={booster_name}"
            )
            return False

        try:
            from ptcgp_auto_v2.utils.pack_image_manager import PackImageManager

            manager = PackImageManager()
            if not self.recognizer:
                logger.error("准备卡包图片资源失败: recognizer 未初始化")
                return False

            _, template_matcher = self.recognizer
            if not manager.ensure_template_ready(template_matcher, booster_name):
                logger.error(f"准备卡包图片资源失败: {booster_name}")
                return False
            logger.debug(f"已预加载目标卡包模板，卡牌系列: {pack_code}")
        except Exception as e:
            logger.error(f"准备卡包图片资源失败: {e}")
            return False

        return True

    def is_completed(self) -> bool:
        """判断任务是否已完成或失败"""
        return self._completed or self._skipped or self._failed

    def was_skipped(self) -> bool:
        """判断任务是否被跳过"""
        return self._skipped

    def handle_page(self, page_name: str, page_info: dict) -> ActionResult:
        """处理识别到的页面"""
        if self._failed:
            return ActionResult.fail(self._fail_reason or "准备卡包图片资源失败")

        logger.debug(f"处理页面: {page_name}")

        # 任务特定页面处理器（优先于通用处理器）
        specific_handlers = {
            "game_home_main": self._handle_home,
            "pack_series_select": self._handle_pack_series_select,
            "pack_list": self._handle_pack_list,
            "pack_detail": self._handle_pack_detail,
            "pack_hourglass_popup": self._handle_hourglass_popup,
        }
        # 合并：特定处理器优先覆盖通用处理器
        handlers = {**self.build_pack_opening_handlers(), **specific_handlers}

        handler = handlers.get(page_name)
        if handler:
            return handler(page_info)

        logger.warning(f"未处理的页面: {page_name}")
        return ActionResult.ok(wait=1.0)

    def handle_unknown_page(self, page_info) -> ActionResult:
        """处理未知页面"""
        logger.debug("未知页面，点击屏幕上方兜底")
        return quick_tap(self.adb, self.adb.center_x(), self.adb.scaled_y(10), times=3)

    def on_complete(self, result: TaskResult):
        """任务完成后的处理"""
        logger.info(
            f"任务完成，已开包: {self._packs_opened_count}, "
            f"结果: {'跳过' if result.skipped else ('成功' if result.success else '失败')}"
        )

        if result.success and not result.skipped and self._packs_opened_count > 0:
            logger.info(f"本次共开 {self._packs_opened_count} 包")

        # 清理开包推断会话资源（无论成功与否）
        self.finalize_pack_session()

    # ============================================================
    # 页面处理方法（任务特定）
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
            "icon_free_pack_available", screenshot=screenshot, threshold=0.8
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

    def _handle_pack_series_select(self, page_info: dict) -> ActionResult:
        """选择扩充包系列"""
        screenshot, ocr_results = self.page_detector.get_last_page_context()

        if not screenshot:
            return ActionResult.fail("截图失败")

        settings = get_settings()
        template_name = self._get_target_template_name()
        if not template_name:
            return ActionResult.fail("未配置目标卡包模板")

        # 确保模板已加载（第一包结束后可能被卸载）
        if self._target_pack:
            booster_name = self._target_pack.get("booster_name")
            if booster_name and self.recognizer:
                from ptcgp_auto_v2.utils.pack_image_manager import PackImageManager

                manager = PackImageManager()
                _, template_matcher = self.recognizer
                manager.ensure_template_ready(template_matcher, booster_name)

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
            base_distance_y=BASE_PACK_SERIES_SCROLL_DISTANCE_Y,
            steps=SWIPE_STEPS_SCROLL,
            wait=1,
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

        # 确保模板已加载（第一包结束后可能被卸载）
        if self._target_pack:
            booster_name = self._target_pack.get("booster_name")
            if booster_name and self.recognizer:
                from ptcgp_auto_v2.utils.pack_image_manager import PackImageManager

                manager = PackImageManager()
                _, template_matcher = self.recognizer
                manager.ensure_template_ready(template_matcher, booster_name)

        # 直接判断当前是否匹配目标包模板
        match = self.page_detector.find_template_with_scale(
            template_name,
            scale=settings.scale_pack_list,
            threshold=settings.pack_template_threshold,
        )

        # 如果不匹配，尝试切换子包
        if not match:
            for attempt in range(len(PACK_SERIES_CODES)):
                logger.info(f"  -> 第 {attempt + 1} 次切换子包")
                tap_right_side(self.adb, wait=1.0)
                screenshot, ocr_results = self.page_detector.capture()
                if not screenshot:
                    continue
                match = self.page_detector.find_template_with_scale(
                    template_name,
                    scale=settings.scale_pack_list,
                    screenshot=screenshot,
                    threshold=settings.pack_template_threshold,
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
        return tap_box(self.adb, match.box, wait=1.0)

    def _extract_pack_points(self, ocr_results: list[dict]) -> None:
        """从 OCR 结果中提取并保存开包点数"""
        if not (self.account.id and self._target_pack and self._pack_point_repo):
            return

        try:
            import re

            for item in ocr_results:
                text = item.get("text", "")
                match = re.search(r"([\d,]+)\s*pt", text, re.IGNORECASE)
                if match:
                    points_str = match.group(1).replace(",", "")
                    points = int(points_str)
                    series = self._target_pack.get("pack_code", "Unknown")
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
        if self._target_pack:
            settings = get_settings()
            template_name = self._get_target_template_name()
            if not template_name:
                return ActionResult.fail("未配置目标卡包模板")

            match = self.page_detector.find_template_with_scale(
                template_name,
                scale=settings.scale_pack_detail,
                screenshot=screenshot,
                threshold=settings.pack_template_threshold,
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

    # ============================================================
    # 辅助方法
    # ============================================================

    def _get_target_series(self) -> Optional[str]:
        """根据 pack_code 获取目标系列（A/B）"""
        if not self._target_pack:
            return None
        pack_code = self._target_pack["pack_code"]
        return pack_code[0].upper() if pack_code else None

    def _get_target_template_name(self) -> Optional[str]:
        """获取目标卡包的模板名称"""
        if not self._target_pack:
            return None
        from ptcgp_auto_v2.utils.pack_image_manager import PackImageManager

        manager = PackImageManager()
        return manager.get_template_name(self._target_pack["booster_name"])
