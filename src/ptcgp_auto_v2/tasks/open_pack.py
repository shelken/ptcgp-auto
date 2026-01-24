# -*- coding: utf-8 -*-
"""
开包任务模块

采用状态机模式管理开包流程，确保任务必须经过主页检查才能结束。
"""

import logging
from datetime import datetime
from enum import Enum, auto
from typing import TYPE_CHECKING, Optional

from ptcgp_auto_v2.config.settings import get_settings
from ptcgp_auto_v2.core.task_base import (
    ActionResult,
    ResetType,
    Task,
    TaskRegistry,
    TaskResult,
)
from ptcgp_auto_v2.locales.zh_Hant import TEXT_PATTERNS


class OpenPackPhase(Enum):
    """开包任务阶段"""

    INIT = auto()  # 初始化，尚未开始
    NAVIGATING_TO_HOME = auto()  # 正在导航到主页
    CHECKING_HOME = auto()  # 在主页检查免费包
    ENTERING_PACK = auto()  # 进入开包流程
    SELECTING_SERIES = auto()  # 选择扩充包系列
    SELECTING_BOOSTER = auto()  # 选择子包
    OPENING = auto()  # 开包动画中
    REGISTERING = auto()  # 卡牌登录图鉴
    PACK_OPENED = auto()  # 成功开了一包
    NO_FREE_PACK = auto()  # 确认无免费包（真正完成）
    SKIPPED = auto()  # 任务被跳过（不更新 last_completed_at）


# 跳过原因常量
SKIP_REASON_NO_ACCOUNT_ID = "账号 ID 为空"
SKIP_REASON_RECENTLY_OPENED = "12 小时内已开包"
SKIP_REASON_NO_PACK_CONFIG = "未配置开包目标"


from ptcgp_auto_v2.utils.gesture import (
    tap_template,
    tap_text,
    tap_center,
    press_back,
    navigate_back,
    swipe,
    long_press,
    long_press_text,
    tap_home_icon,
    click_close,
    tap_bottom_close,
    tap_box,
    center_point,
    swipe_pack_coords,
    swipe_card_coords,
    tap_template_or_text,
    tap_template_with_scale,
    scroll_until_template,
    cycle_until_template,
)

if TYPE_CHECKING:
    from ptcgp_auto_v2.db.repositories import (
        AccountPackConfigRepository,
        PackRecordRepository,
        TaskInstanceRepository,
    )

logger = logging.getLogger(__name__)

# ============================================================
# 常量定义（基于 1080x1920 基准分辨率的像素值）
# 使用时通过 adb.scaled_x/scaled_y 缩放到当前分辨率
# ============================================================

# 沙漏弹窗关闭点击位置（屏幕底部区域）
# 1920 * 0.95 ≈ 1824，取 1820
BASE_POPUP_CLOSE_TAP_Y = 1820

# 开包滑动时长 (ms)
SWIPE_DURATION_OPEN = 500
# 登录图鉴滑动时长 (ms)
SWIPE_DURATION_REGISTER = 300


def _get_patterns(text_patterns: dict, key: str) -> list[str]:
    """获取指定配置的文本列表"""
    patterns = text_patterns.get(key, [])
    if isinstance(patterns, list):
        return patterns
    return []


# ============================================================
# 页面识别规则
# 注意：priority 数值越小优先级越高
# ============================================================
def _build_pack_pages(text_patterns: dict) -> list[dict]:
    """构建开包任务页面规则"""
    return [
        {
            "name": "pack_series_select",
            "identifiers": _get_patterns(text_patterns, "pack_series_select"),
            "priority": 99,
            "exact_match": True,
        },
        {
            "name": "pack_list",
            "identifiers": _get_patterns(text_patterns, "pack_list"),
            "match_all": True,
            "exclude_identifiers": _get_patterns(text_patterns, "pack_list_exclude"),
            "priority": 99,
        },
        {
            "name": "pack_opening_swipe",
            "identifiers": _get_patterns(text_patterns, "pack_opening_swipe"),
            "priority": 99,
        },
        {
            "name": "pack_opening_select",
            "identifiers": _get_patterns(text_patterns, "pack_opening_select"),
            "priority": 99,
        },
        {
            "name": "pack_opening_card",
            "identifiers": _get_patterns(text_patterns, "long_press"),
            "priority": 99,
        },
        {
            "name": "pack_opening_result",
            "identifiers": _get_patterns(text_patterns, "pack_opening_result"),
            "priority": 99,
        },
        {
            "name": "pack_card_register",
            "identifiers": _get_patterns(text_patterns, "pack_card_register"),
            "priority": 99,
        },
        {
            "name": "pack_detail",
            "identifiers": _get_patterns(text_patterns, "open_pack"),
            "exclude_identifiers": _get_patterns(text_patterns, "open_pack_exclude"),
            "priority": 99,
            "exact_match": True,
        },
        {
            "name": "pack_hourglass_popup",
            "identifiers": _get_patterns(text_patterns, "pack_hourglass_popup"),
            "priority": 99,
        },
        {
            "name": "pack_paid_detail",
            "identifiers": _get_patterns(text_patterns, "pack_paid_detail"),
            "priority": 99,
        },
        {
            "name": "game_home_main",
            "match_all": True,
            "identifiers": _get_patterns(text_patterns, "game_home_main"),
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

    使用状态机管理开包流程，确保：
    1. 任务必须经过主页检查
    2. 只有在主页确认无免费包（连续 N 次）或成功开包才结束
    """

    task_type = "open_pack"
    reset_type = ResetType.DAILY
    max_iterations = 100
    max_unknown_pages = 15
    pages = _build_pack_pages(TEXT_PATTERNS)

    # 主页检查次数阈值
    HOME_CHECK_THRESHOLD = 3

    def __init__(self, adb, recognizer, page_detector):
        super().__init__(adb, recognizer, page_detector)

        # 初始化卡牌识别器
        from ptcgp_auto_v2.infra.card_recognizer import CardRecognizer
        # recognizer 是 (ocr_engine, template_matcher) 元组
        _, template_matcher = recognizer
        self.card_recognizer = CardRecognizer(adb, template_matcher)

        # 核心状态机
        self._phase = OpenPackPhase.INIT
        self._home_check_count = 0  # 主页无免费包检查次数
        self._packs_opened_count = 0  # 本次任务已开包数量
        self._result_recognized = False  # 本次开包是否已识别结果
        self._skip_reason: Optional[str] = None  # 跳过原因

        # 目标卡包配置
        self.target_pack = None  # {"pack_code": "A1", "booster_name": "Charizard"}
        self._boosters_list = []  # 子包列表

        # 数据仓储（延迟加载）
        self._pack_config_repo: "AccountPackConfigRepository | None" = None
        self._pack_record_repo: "PackRecordRepository | None" = None
        self._task_instance_repo: "TaskInstanceRepository | None" = None

    def on_start(self):
        """
        任务开始前的初始化

        检查数据库记录和加载配置，设置初始阶段。
        """
        from ptcgp_auto_v2.db.repositories import (
            AccountPackConfigRepository,
            PackRecordRepository,
            TaskInstanceRepository,
        )

        # 初始化仓储
        self._pack_config_repo = AccountPackConfigRepository()
        self._pack_record_repo = PackRecordRepository()
        self._task_instance_repo = TaskInstanceRepository()

        # 1. 检查账号 ID
        if self.account.id is None:
            logger.error(f"账号 {self.account.display_name} ID 为空")
            self._phase = OpenPackPhase.SKIPPED
            self._skip_reason = SKIP_REASON_NO_ACCOUNT_ID
            return

        # 2. 检查 12 小时内是否已开包
        if self._pack_record_repo.has_opened_within_hours(self.account.id, hours=12):
            logger.info(f"账号 {self.account.display_name} 12 小时内已开包，任务跳过")
            self._phase = OpenPackPhase.SKIPPED
            self._skip_reason = SKIP_REASON_RECENTLY_OPENED
            return

        # 3. 加载开包配置
        config = self._pack_config_repo.get_by_account_and_type(
            self.account.id, "daily"
        )
        if not config:
            logger.info(f"账号 {self.account.display_name} 未配置开包目标，任务跳过")
            self._phase = OpenPackPhase.SKIPPED
            self._skip_reason = SKIP_REASON_NO_PACK_CONFIG
            return

        self.target_pack = {
            "pack_code": config.pack_code,
            "booster_name": config.booster_name,
        }
        logger.info(f"目标卡包: {config.pack_code}/{config.booster_name}")

        # 4. 准备图片资源 (按需加载)
        try:
            from ptcgp_auto_v2.utils.image_manager import ImageResourceManager

            manager = ImageResourceManager()
            pack_code = config.pack_code
            booster_name = config.booster_name

            # 1. 下载/处理图片
            manager.ensure_pack_ready(booster_name, pack_code)

            # 2. 加载特定卡包的模板到匹配器
            if self.recognizer:
                _, template_matcher = self.recognizer
                template_matcher.load_pack_templates(pack_code, booster_name)

        except Exception as e:
            logger.error(f"准备图片资源失败: {e}")

        # 5. 加载子包列表
        self._boosters_list = self._load_boosters_list(config.pack_code)

        # 6. 进入导航阶段
        self._phase = OpenPackPhase.NAVIGATING_TO_HOME
        logger.info(f"开包任务开始，当前阶段: {self._phase.name}")

    def is_completed(self) -> bool:
        """
        判断任务是否已完成

        结束条件：
        - 在主页确认无免费包（真正完成）
        - 任务被跳过（SKIPPED）
        """
        return self._phase in (OpenPackPhase.NO_FREE_PACK, OpenPackPhase.SKIPPED)

    def was_skipped(self) -> bool:
        """判断任务是否被跳过（用于 Task.execute 判断是否更新 last_completed_at）"""
        return self._phase == OpenPackPhase.SKIPPED

    def handle_page(self, page_name: str, page_info: dict) -> ActionResult:
        """
        处理识别到的页面

        根据当前页面执行相应动作，并更新状态机阶段。
        """
        logger.debug(f"处理页面: {page_name}, 当前阶段: {self._phase.name}")

        # 主页：核心决策点，检查免费包
        if page_name == "game_home_main":
            return self._handle_home(page_info)

        # home_icon：点击底部主页图标回到游戏主页
        if page_name == "home_icon":
            logger.debug("  -> 点击主页图标回到游戏主页")
            return tap_home_icon(self.adb, self.page_detector, wait=1.0)

        # pack_series_select：选择扩充包系列
        if page_name == "pack_series_select":
            self._phase = OpenPackPhase.SELECTING_SERIES
            return self._handle_pack_series_select(page_info)

        # pack_list：选择子包
        if page_name == "pack_list":
            self._phase = OpenPackPhase.SELECTING_BOOSTER
            return self._handle_pack_list(page_info)

        # pack_detail：点击开封
        if page_name == "pack_detail":
            return self._handle_pack_detail(page_info)

        # pack_hourglass_popup：处理沙漏弹窗
        if page_name == "pack_hourglass_popup":
            return self._handle_hourglass_popup(page_info)

        # pack_opening_swipe：滑动开包
        if page_name == "pack_opening_swipe":
            self._phase = OpenPackPhase.OPENING
            return self._handle_opening_swipe(page_info)

        # pack_opening_card：长按跳过卡牌
        if page_name == "pack_opening_card":
            self._phase = OpenPackPhase.OPENING
            return self._handle_opening_card(page_info)

        # pack_card_register：上滑登录图鉴
        if page_name == "pack_card_register":
            self._phase = OpenPackPhase.REGISTERING
            return self._handle_card_register(page_info)

        # pack_opening_result：识别结果并点击继续
        if page_name == "pack_opening_result":
            return self._handle_pack_opening_result(page_info)

        # pack_opening_select：点击选择要开的扩充包
        if page_name == "pack_opening_select":
            self._phase = OpenPackPhase.OPENING
            logger.debug("  -> 点击屏幕中心选择扩充包")
            return tap_center(self.adb, wait=1.0)

        # 其他页面由通用处理器处理
        logger.warning(
            f"未处理的页面: {page_name}, 已注册处理器: {list(self._handlers.keys())}"
        )
        return ActionResult.fail(f"未处理的页面: {page_name}")

    def on_complete(self, result: TaskResult):
        """
        任务完成后的处理

        状态更新由 executor 统一处理，此处仅负责创建开包记录。
        """
        logger.info(
            f"任务完成，阶段: {self._phase.name}, 已开包: {self._packs_opened_count}, "
            f"结果: {'跳过' if result.skipped else ('成功' if result.success else '失败')}"
        )

        if self.account.id is None:
            logger.error(f"账号 {self.account.display_name} ID 为空，无法创建记录")
            return

        # 只有真正完成且开过包才创建记录
        if (
            result.success
            and not result.skipped
            and self._packs_opened_count > 0
            and self._pack_record_repo
            and self.target_pack
        ):
            pack_type = (
                f"{self.target_pack['pack_code']}/{self.target_pack['booster_name']}"
            )
            self._pack_record_repo.create_for_account(
                self.account.id,
                pack_type=pack_type,
                cards=self._current_pack_cards
            )
            logger.info(
                f"已创建开包记录: {pack_type}（本次共开 {self._packs_opened_count} 包）"
            )
        elif result.success and not result.skipped:
            logger.info("任务完成（无免费包），不创建开包记录")

        # 清理卡包模板资源
        if self.recognizer:
            try:
                _, template_matcher = self.recognizer
                template_matcher.unload_pack_templates()
            except Exception as e:
                logger.warning(f"卸载卡包模板失败: {e}")

    def _handle_home(self, page_info: dict) -> ActionResult:
        """
        处理主页：核心决策点

        这是任务的核心逻辑：
        1. 设置阶段为 CHECKING_HOME
        2. 检查是否有免费包图标
        3. 有免费包 → 进入开包流程
        4. 无免费包 → 累计计数，达到阈值则设置 NO_FREE_PACK
        """
        self._phase = OpenPackPhase.CHECKING_HOME
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
            self._phase = OpenPackPhase.ENTERING_PACK

            # 点击开包入口图标
            pack_open_box = self.page_detector.find_template_with_scale(
                "icon_pack_open", screenshot=screenshot
            )
            if pack_open_box:
                return tap_box(self.adb, pack_open_box.box, wait=1.0)
            logger.warning("  -> 未找到开包图标，跳过点击免费包图标")
            return ActionResult.ok(wait=1.0)

        # 无免费包，累计计数
        self._home_check_count += 1
        logger.debug(
            f"  -> 未检测到免费包 ({self._home_check_count}/{self.HOME_CHECK_THRESHOLD})"
        )

        if self._home_check_count >= self.HOME_CHECK_THRESHOLD:
            logger.debug("  -> 确认无免费包，任务完成")
            self._phase = OpenPackPhase.NO_FREE_PACK

        return ActionResult.ok(wait=1.0)

    def _handle_pack_series_select(self, page_info: dict) -> ActionResult:
        """选择扩充包系列（pack_series_select 页面）"""
        screenshot, ocr_results = self.page_detector.get_last_page_context()

        if not screenshot:
            return ActionResult.fail("截图失败")

        settings = get_settings()
        template_name = self._get_target_template_name()

        # 1. 模板匹配查找目标扩充包（优先）
        result = tap_template_with_scale(
            self.page_detector,
            template_name,
            scale=settings.scale_pack_series_select,
            wait=1.0,
        )
        if result:
            logger.debug("  -> 找到目标扩充包，点击进入")
            return result

        # 2. 尝试切换到目标系列
        target_series = self._get_target_series()
        if target_series:
            series_patterns = TEXT_PATTERNS.get("series", {})
            if target_series in series_patterns:
                patterns = series_patterns[target_series]
                result = tap_template_or_text(
                    self.adb,
                    self.page_detector,
                    ocr_results,
                    None,
                    patterns,
                    wait=1.0,
                )
                if result:
                    logger.debug(f"  -> 点击切换到 {target_series} 系列")
                    return result

        # 3. 上滑查找
        max_attempts = settings.max_scroll_attempts
        result = scroll_until_template(
            self.page_detector,
            template_name,
            scale=settings.scale_pack_series_select,
            max_attempts=max_attempts,
            swipe_ratio=0.21,
            wait=1.2,
        )
        if result:
            return result

        # 未找到，返回上一页
        return navigate_back(
            self.adb, self.page_detector, ocr_results, TEXT_PATTERNS["back_button"]
        )

    def _handle_pack_list(self, page_info: dict) -> ActionResult:
        """选择子包（pack_list 页面）"""
        screenshot, ocr_results = self.page_detector.get_last_page_context()

        if not screenshot:
            return ActionResult.fail("截图失败")

        settings = get_settings()
        template_name = self._get_target_template_name()

        # 1. 先检查当前是否是目标子包
        result = tap_template_with_scale(
            self.page_detector,
            template_name,
            scale=settings.scale_pack_list,
            wait=1.0,
        )
        if result:
            logger.debug("  -> 当前是目标子包，点击进入详情")
            return result

        # 2. 点击右侧切换子包，最多切换到子包数量
        result = cycle_until_template(
            self.page_detector,
            template_name,
            scale=settings.scale_pack_list,
            max_attempts=len(self._boosters_list),
            wait=1.0,
        )
        if result:
            logger.debug("  -> 找到目标子包，点击进入详情")
            return result

        # 未找到，返回上一页
        return navigate_back(
            self.adb, self.page_detector, ocr_results, TEXT_PATTERNS["back_button"]
        )

    def _handle_pack_detail(self, page_info: dict) -> ActionResult:
        """
        点击开包按钮（pack_detail 页面）

        1. 检查当前卡包是否是目标卡包（模板匹配）
        2. 检查是否是付费包
        3. 点击开封按钮
        """
        screenshot, ocr_results = self.page_detector.get_last_page_context()

        if not screenshot:
            return ActionResult.fail("截图失败")

        # 1. 检查当前卡包是否是目标卡包（模板匹配）
        if self.target_pack:
            settings = get_settings()
            template_name = self._get_target_template_name()

            match = self.page_detector.find_template_with_scale(
                template_name,
                scale=settings.scale_pack_detail,
                screenshot=screenshot,
            )
            if not match:
                logger.info(
                    f"  -> 当前卡包不是目标卡包 ({template_name})，返回主页重新寻找"
                )
                return navigate_back(
                    self.adb,
                    self.page_detector,
                    ocr_results,
                    TEXT_PATTERNS["back_button"],
                )

        # 2. 检查是否是付费包（需要消耗沙漏的包）
        paid_patterns = TEXT_PATTERNS.get("open_pack_1", [])
        if paid_patterns and any(
            pattern in item["text"] for pattern in paid_patterns for item in ocr_results
        ):
            logger.info("  -> 检测到付费包，返回上一页")
            return navigate_back(
                self.adb,
                self.page_detector,
                ocr_results,
                TEXT_PATTERNS["back_button"],
            )

        # 3. 点击"開封"按钮
        open_pack_patterns = TEXT_PATTERNS.get("open_pack", [])
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
            self._phase = OpenPackPhase.OPENING
            return result

        logger.warning("  -> 未找到开包按钮")
        return ActionResult.ok(wait=1.0)

    def _handle_hourglass_popup(self, page_info: dict) -> ActionResult:
        """处理沙漏弹窗（pack_hourglass_popup 页面）"""
        ocr_results = page_info.get("ocr_results", [])
        close_patterns = TEXT_PATTERNS.get("close_button", [])

        result = click_close(self.adb, self.page_detector, ocr_results, close_patterns)
        if result:
            logger.info("  -> 点击关闭弹窗")
            return result

        logger.info("  -> 点击屏幕底部关闭弹窗")
        return tap_bottom_close(self.adb, BASE_POPUP_CLOSE_TAP_Y, wait=1.0)

    def _handle_opening_swipe(self, page_info: dict) -> ActionResult:
        """滑动开包（pack_opening_swipe 页面）"""
        logger.info("  -> 从左往右滑动开包")
        # 进入 滑动开包 说明开包成功，增加计数
        self._packs_opened_count += 1
        # 重置识别标志位
        self._result_recognized = False
        start, end = swipe_pack_coords(self.adb)
        return swipe(self.adb, start, end, duration=SWIPE_DURATION_OPEN)

    def _handle_opening_card(self, page_info: dict) -> ActionResult:
        """
        长按"長按"文字位置跳过卡牌展示（pack_opening_card 页面）
        """
        ocr_results = page_info.get("ocr_results", [])
        long_press_patterns = TEXT_PATTERNS.get("long_press", [])

        # 使用工具函数长按文字位置
        result = long_press_text(self.adb, ocr_results, long_press_patterns)
        if result:
            logger.info("  -> 长按文字跳过卡牌展示")
            return result

        # fallback 到屏幕中心
        logger.warning("  -> 未找到長按文字，长按屏幕中心")

        # 开包流程即将结束，准备回到主页继续检测
        self._phase = OpenPackPhase.NAVIGATING_TO_HOME
        self._home_check_count = 0  # 重置主页检查计数

        return long_press(self.adb, center_point(self.adb))

    def _handle_card_register(self, page_info: dict) -> ActionResult:
        """向上滑动卡牌登录图鉴（pack_card_register 页面）仅在有新卡时出现"""
        logger.info(f"  -> 向上滑动卡牌（已开 {self._packs_opened_count} 包）")
        start, end = swipe_card_coords(self.adb)
        return swipe(self.adb, start, end, duration=SWIPE_DURATION_REGISTER)

    def _load_boosters_list(self, pack_code: str) -> list:
        """从 packs.json 加载子包列表"""
        from ptcgp_auto_v2.utils.packs import get_boosters

        boosters = get_boosters(pack_code)
        logger.info(f"系列 {pack_code} 有 {len(boosters)} 个子包: {boosters}")
        return boosters

    def _get_target_template_name(self) -> Optional[str]:
        """获取目标卡包的模板名称"""
        if not self.target_pack:
            return None
        # 模板文件名使用下划线，需要将空格替换为下划线
        booster_name = self.target_pack["booster_name"].replace(" ", "_")
        return f"packs/{self.target_pack['pack_code']}/{booster_name}"

    def _handle_pack_opening_result(self, page_info: dict) -> ActionResult:
        """
        处理开包结果页（pack_opening_result）

        1. 识别卡牌（如果尚未识别）
        2. 点击屏幕中心继续
        """
        if not self._result_recognized:
            try:
                # 调用 Infra 层服务进行识别
                cards = self.card_recognizer.analyze_result_screen()
                if cards:
                    card_names = [f"{c.name}({c.confidence:.2f})" for c in cards]
                    logger.info(f"====== 识别到 {len(cards)} 张卡牌 ======")
                    for c in cards:
                        logger.info(f"  - {c.name} (Conf: {c.confidence:.2f})")
                    logger.info("==================================")
                else:
                    logger.info("未识别到卡牌")
            except Exception as e:
                logger.error(f"识别卡牌失败: {e}")
            finally:
                self._result_recognized = True

        logger.debug("  -> 点击屏幕中心继续")
        return tap_center(self.adb, wait=1.5)
