# -*- coding: utf-8 -*-
"""
开包任务模块

采用字典映射处理页面，使用 action_cache 管理页面内操作状态。
流程：主页检测免费包 → 选择系列 → 选择子包 → 开包 → 登录图鉴 → 回到主页检查

继承 PackOpeningTaskBase，复用统一开包流程，保留主页与选包业务入口。
"""

import logging
from typing import TYPE_CHECKING, Optional, cast

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
from ptcgp_auto_v2.db.models import PackRecordType
from ptcgp_auto_v2.locales import get_config_value, get_text_patterns
from ptcgp_auto_v2.tasks.pack_opening_task_base import (
    PACK_RESULT_MODE_TEN,
    PackOpeningTaskBase,
    build_pack_opening_pages,
)
from ptcgp_auto_v2.utils.gesture import (
    click_close,
    navigate_back,
    quick_tap,
    scroll_until_template,
    tap_box,
    tap_ok,
    tap_right_side,
    tap_template_with_scale,
    tap_text_exact,
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

# 開封10包需要消耗的沙漏数量
OPEN_10_PACK_HOURGLASS_COST = 120

# 開封10包的实际包数
OPEN_10_PACK_BATCH_SIZE = 10

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
        # 付费包检测（開封1包）- 免费包开完后出现
        {
            "name": "pack_paid",
            "identifiers": get_text_patterns("open_pack_1"),
            "priority": 99,
            "exact_match": True,
        },
        # 付费包确认弹窗（要使用道具）
        {
            "name": "pack_paid_modal",
            "identifiers": get_text_patterns("use_item_confirm"),
            "priority": 99,
            "exact_match": True,
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
    # 实测 66 左右
    max_iterations = 120
    pages = _build_open_pack_pages()

    def __init__(self, adb, recognizer, page_detector):
        super().__init__(adb, recognizer, page_detector)

        # 数据仓储（基类已初始化，此处仅用于类型提示）
        self._pack_config_repo = None
        self._account_stat_repo = None

    # ============================================================
    # 扩展点实现（PackOpeningTaskBase 要求）
    # ============================================================

    def get_pack_record_type(self) -> str:
        """返回 pack 记录类型：免费单包或十连开包。"""
        if self._pack_result_mode == PACK_RESULT_MODE_TEN:
            return PackRecordType.TEN_PACK
        return PackRecordType.DAILY_FREE

    def get_rare_card_notify_message(self) -> str:
        """返回稀有卡通知消息：每日开包"""
        return "开包获得稀有卡牌"

    def get_target_pack_context(self) -> dict[str, str] | None:
        """获取目标卡包上下文"""
        return cast(dict[str, str] | None, self.state_get("target_pack"))

    def should_prepare_pack_resources(self) -> bool:
        """open_pack 需要准备卡包图片资源"""
        return True

    # ============================================================
    # 任务生命周期
    # ============================================================

    def on_start(self):
        """任务开始前的初始化"""
        from ptcgp_auto_v2.db.repositories import (
            AccountPackConfigRepository,
            AccountStatRepository,
        )

        self._init_repositories()
        self._pack_config_repo = AccountPackConfigRepository()
        self._account_stat_repo = AccountStatRepository()

        self.state.reset()
        self.state_update(
            {
                "state_cache": {},
                "home_check_count": 0,
                "pack_hourglass_count": None,
                "target_pack": None,
            }
        )
        self._packs_opened_count = 0
        self._result_recognized = False
        self._base_pack_points = None  # 重置基础开包点数
        self._reset_pack_result_mode()

        # 检查账号 ID
        if self.account.id is None:
            logger.error(f"账号 {self.account.display_name} ID 为空")
            self.skip("账号ID为空")
            return

        self.state_set("pack_hourglass_count", self._load_pack_hourglass_count())
        logger.info(
            "当前开包沙漏数量: %s",
            cast(int | None, self.state_get("pack_hourglass_count")),
        )

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
                self.skip("无法找到可用的开包目标")
                return

            self.state_set(
                "target_pack",
                {
                    "set_code": selected["set_code"],
                    "booster_name": selected["booster_name"],
                },
            )
            logger.info(
                "自动选择卡包: %s/%s (策略=%s, 候选=%s)",
                selected["set_code"],
                selected["booster_name"],
                selected.get("strategy"),
                selected.get("candidate_count"),
            )
        else:
            self.state_set(
                "target_pack",
                {"set_code": config.set_code, "booster_name": config.booster_name},
            )
            logger.info(f"目标卡包: {config.set_code}/{config.booster_name}")

        # 准备图片资源
        if self.should_prepare_pack_resources():
            if not self._prepare_image_resources():
                logger.error("准备卡包图片资源失败")
                self.fail("准备卡包图片资源失败")
                return

        # 预加载目标系列 Hash
        self._preload_target_series_hash()

    def _prepare_image_resources(self) -> bool:
        """准备图片资源（失败将直接结束任务）"""
        target_pack = cast(dict[str, str] | None, self.state_get("target_pack"))
        set_code = target_pack.get("set_code") if target_pack else None
        booster_name = target_pack.get("booster_name") if target_pack else None
        if not set_code or not booster_name:
            logger.error(
                f"准备卡包图片资源失败: set_code={set_code}, booster_name={booster_name}"
            )
            return False

        try:
            if not self.recognizer:
                logger.error("准备卡包图片资源失败: recognizer 未初始化")
                return False

            from ptcgp_auto_v2.tasks.utils.pack_template_matcher import (
                PackCandidate,
                build_pack_template_matcher,
            )

            if self._pack_template_matcher is None:
                self._pack_template_matcher = build_pack_template_matcher(
                    self.recognizer
                )

            matcher = self._pack_template_matcher
            if matcher is None:
                logger.error("准备卡包图片资源失败: pack 模板匹配器未初始化")
                return False

            ready = matcher.prepare(
                [PackCandidate(set_code=str(set_code), booster_name=str(booster_name))]
            )
            if not ready.get(str(booster_name), False):
                logger.error(f"准备卡包图片资源失败: {booster_name}")
                return False
            logger.debug(f"已预加载目标卡包模板，卡牌系列: {set_code}")
        except Exception as e:
            logger.error(f"准备卡包图片资源失败: {e}")
            return False

        return True

    def handle_unmapped_page(self, page_name: str, page_info: dict) -> ActionResult:
        if self.is_failed():
            return ActionResult.fail(self.get_error() or "准备卡包图片资源失败")

        logger.debug(f"处理页面: {page_name}")
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

    def _handle_game_home_main(self, page_info: dict) -> ActionResult:
        """处理主页：核心决策点，检查免费包"""
        self.reset_action_cache()
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
            self.state_set("home_check_count", 0)
            return self._tap_pack_open_icon(screenshot)

        if self._has_completed_10_pack_this_task():
            logger.debug("  -> 十包流程已完成，任务结束")
            self.complete()
            return ActionResult.ok(wait=1.0)

        if self._should_exit_pack_flow_after_free_packs():
            logger.debug("  -> 免费包已开完且无需十包，任务结束")
            self.complete()
            return ActionResult.ok(wait=1.0)

        if self._can_open_10_pack() and not self._has_started_10_pack_this_task():
            logger.debug("  -> 无免费包但满足10包条件，进入开包流程")
            self.state_set("home_check_count", 0)
            return self._tap_pack_open_icon(screenshot)

        # 无免费包，累计计数
        home_check_count = int(self.state_get("home_check_count", 0)) + 1
        self.state_set("home_check_count", home_check_count)
        logger.debug(f"  -> 未检测到免费包 ({home_check_count}/{HOME_CHECK_THRESHOLD})")

        if home_check_count >= HOME_CHECK_THRESHOLD:
            logger.debug("  -> 确认无免费包，任务完成")
            self.complete()

        return ActionResult.ok(wait=1.0)

    def _tap_pack_open_icon(self, screenshot) -> ActionResult:
        """点击主页开包入口图标。"""
        pack_open_box = self.page_detector.find_template_with_scale(
            "icon_pack_open", screenshot=screenshot
        )
        if pack_open_box:
            return tap_box(self.adb, pack_open_box.box, wait=1.0)
        logger.warning("  -> 未找到开包图标")
        return ActionResult.ok(wait=1.0)

    def _should_exit_pack_flow(self) -> bool:
        """十包完成后退出选包链路，避免在列表和详情页之间反复往返。"""
        return (
            self._has_completed_10_pack_this_task()
            or self._should_exit_pack_flow_after_free_packs()
        )

    def _is_open_10_pack_enabled(self) -> bool:
        """是否启用十包开封模式。"""
        return get_settings().enable_open_10_pack

    def _handle_pack_series_select(self, page_info: dict) -> ActionResult:
        """选择扩充包系列"""
        screenshot, ocr_results = self.page_detector.get_last_page_context()

        if not screenshot:
            return ActionResult.fail("截图失败")

        if self._should_exit_pack_flow():
            logger.debug("  -> 十包流程已完成，退出扩充包系列页")
            return navigate_back(self.adb, self.page_detector, ocr_results)

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
            self.reset_action_cache()
            return result

        # 2. 尝试切换到目标系列
        target_series = self._get_target_series()
        if target_series and not self.is_action_done("series_clicked"):
            series_patterns = get_config_value("series")
            if isinstance(series_patterns, dict) and target_series in series_patterns:
                patterns = series_patterns[target_series]
                result = tap_text_exact(self.adb, ocr_results, patterns, wait=1.0)
                if result:
                    self.mark_action_done("series_clicked")
                    logger.info(f"  -> 点击切换到 {target_series} 系列")
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
        return navigate_back(self.adb, self.page_detector, ocr_results)

    def _handle_pack_list(self, page_info: dict) -> ActionResult:
        """选择子包"""
        screenshot, ocr_results = self.page_detector.get_last_page_context()

        if not screenshot:
            return ActionResult.fail("截图失败")

        if self._should_exit_pack_flow():
            logger.debug("  -> 十包流程已完成，退出子包选择页")
            return navigate_back(self.adb, self.page_detector, ocr_results)

        settings = get_settings()
        template_name = self._get_target_template_name()
        if not template_name:
            return ActionResult.fail("未配置目标卡包模板")

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
                logger.debug("  -> 循环切换子包未找到目标，返回上一页")
                return navigate_back(self.adb, self.page_detector, ocr_results)

        # 匹配成功，提取基础点数（延迟更新，等保存记录时再累加）
        self._extract_pack_points(ocr_results)

        # 点击进入详情
        logger.debug("  -> 找到目标子包，点击进入详情")
        self.reset_action_cache()
        return tap_box(self.adb, match.box, wait=1.0)

    def _extract_pack_points(self, ocr_results: list[dict]) -> None:
        """从 OCR 结果中提取开包点数并保存到基类变量（延迟到保存记录时更新数据库）"""
        target_pack = cast(dict[str, str] | None, self.state_get("target_pack"))
        if not (self.account.id and target_pack):
            return

        try:
            import re

            # set_code 表示系列代码，缺失时不允许写入 Unknown
            set_code = target_pack.get("set_code")
            if not set_code:
                logger.warning("  -> 提取开包点数失败: 目标卡包缺少 set_code")
                return

            for item in ocr_results:
                text = item.get("text", "")
                match = re.search(r"([\d,]+)\s*pt", text, re.IGNORECASE)
                if match:
                    points_str = match.group(1).replace(",", "")
                    points = int(points_str)
                    # 保存到基类变量，延迟到保存记录时更新
                    self._base_pack_points = points
                    logger.info(
                        f"  -> 提取到基础开包点数: {set_code} = {points}pt（将在保存记录时累加）"
                    )
                    break
        except Exception as e:
            logger.warning(f"  -> 提取开包点数失败: {e}")

    def _handle_pack_detail(self, page_info: dict) -> ActionResult:
        """点击开包按钮"""
        screenshot, ocr_results = self.page_detector.get_last_page_context()

        if not screenshot:
            return ActionResult.fail("截图失败")

        if self._should_exit_pack_flow():
            logger.debug("  -> 十包流程已完成，退出卡包详情页")
            return navigate_back(self.adb, self.page_detector, ocr_results)

        # 检查当前卡包是否是目标卡包
        target_pack = cast(dict[str, str] | None, self.state_get("target_pack"))
        if target_pack:
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
                return navigate_back(self.adb, self.page_detector, ocr_results)

        # 点击"開封"按钮
        result = tap_text_exact(
            self.adb,
            ocr_results,
            get_text_patterns("open_pack"),
            wait=1.0,
        )
        if result:
            logger.info("  -> 点击开封按钮，进入开包流程")
            return result

        logger.warning("  -> 未找到开包按钮")
        return ActionResult.ok(wait=1.0)

    def _handle_pack_paid(self, page_info: dict) -> ActionResult:
        """处理付费包页面（開封1包）- 检查沙漏数量决定是否开10包"""
        ocr_results = page_info.get("ocr_results", [])

        if self._has_started_10_pack_this_task():
            logger.debug("  -> 已使用过開封10包，返回上一页")
            return navigate_back(self.adb, self.page_detector, ocr_results)

        if not self._is_open_10_pack_enabled():
            self._set_state_flag("pack_flow", "exit_after_paid")
            logger.debug("  -> 已关闭開封10包模式，返回上一页")
            return navigate_back(self.adb, self.page_detector, ocr_results)

        if not self._can_open_10_pack():
            self._set_state_flag("pack_flow", "exit_after_paid")
            logger.info(
                "  -> 沙漏数量 %s < %s，不满足开10包条件",
                cast(int | None, self.state_get("pack_hourglass_count")),
                OPEN_10_PACK_HOURGLASS_COST,
            )
            return navigate_back(self.adb, self.page_detector, ocr_results)

        logger.info(
            "  -> 沙漏数量 %s >= %s，准备开10包",
            cast(int | None, self.state_get("pack_hourglass_count")),
            OPEN_10_PACK_HOURGLASS_COST,
        )

        # 点击開封10包按钮
        result = tap_text_exact(
            self.adb,
            ocr_results,
            get_text_patterns("open_pack_10"),
            wait=1.5,
        )
        if result:
            logger.info("  -> 点击開封10包按钮")
            return result

        logger.warning("  -> 未找到開封10包按钮")
        return ActionResult.ok(wait=1.0)

    def _handle_pack_paid_modal(self, page_info: dict) -> ActionResult:
        """处理付费包确认弹窗（要使用道具）"""
        ocr_results = page_info.get("ocr_results", [])

        if self._should_confirm_10_pack_modal():
            result = tap_ok(self.adb, ocr_results, wait=2.0)
            if result:
                self._set_state_flag("ten_pack", "confirmed")
                self._set_pack_result_mode(OPEN_10_PACK_BATCH_SIZE)
                self._consume_pack_hourglasses(OPEN_10_PACK_HOURGLASS_COST)
                logger.info("  -> 点击OK确认使用沙漏开10包")
                return result

            logger.warning("  -> 未找到OK按钮")
            return ActionResult.ok(wait=1.0)

        # 不需要开10包，点击关闭弹窗
        logger.debug("  -> 不需要开10包，关闭弹窗")
        close_patterns = get_text_patterns("close_button")
        result = click_close(self.adb, self.page_detector, ocr_results, close_patterns)
        if result:
            return result

        return ActionResult.ok(wait=1.0)

    def _handle_pack_opening_result(self, page_info: dict) -> ActionResult:
        """处理开包结果页，并在十包完整结束后标记任务可退出。"""
        is_ten_pack_result = self._pack_result_mode == PACK_RESULT_MODE_TEN
        result = super()._handle_pack_opening_result(page_info)

        if is_ten_pack_result and self._result_recognized:
            self._set_state_flag("ten_pack", "completed")

        return result

    def _get_state_group(self, group: str) -> dict[str, bool]:
        """获取任务状态分组缓存。"""
        state_cache = cast(
            dict[str, dict[str, bool]], self.state_get("state_cache", {})
        )
        state = state_cache.get(group)
        if state is None:
            state = {}
            state_cache[group] = state
            self.state_set("state_cache", state_cache)
        return state

    def _set_state_flag(self, group: str, key: str, value: bool = True) -> None:
        """设置任务状态标记。"""
        self._get_state_group(group)[key] = value

    def _get_state_flag(self, group: str, key: str) -> bool:
        """读取任务状态标记。"""
        return self._get_state_group(group).get(key, False)

    def _load_pack_hourglass_count(self) -> int | None:
        """任务开始时读取一次当前账号沙漏数量。"""
        if not self.account.id or self._account_stat_repo is None:
            return None

        try:
            stat = self._account_stat_repo.get_by_account_id(self.account.id)
            if stat:
                return stat.pack_hourglass_count
        except Exception as e:
            logger.warning(f"  -> 获取沙漏数量失败: {e}")

        return None

    def _consume_pack_hourglasses(self, amount: int) -> None:
        """扣减本地缓存和账号统计中的开包沙漏数量。"""
        if amount <= 0:
            return

        pack_hourglass_count = cast(int | None, self.state_get("pack_hourglass_count"))
        if pack_hourglass_count is not None:
            self.state_set(
                "pack_hourglass_count", max(0, pack_hourglass_count - amount)
            )

        if not self.account.id or self._account_stat_repo is None:
            return

        try:
            row = self._account_stat_repo.decrease_pack_hourglass_count(
                self.account.id,
                amount,
            )
            if row is not None and row.pack_hourglass_count is not None:
                self.state_set("pack_hourglass_count", row.pack_hourglass_count)
        except Exception as e:
            logger.warning(f"  -> 扣减开包沙漏失败: {e}")

    def _can_open_10_pack(self) -> bool:
        """判断当前缓存的沙漏数量是否满足開封10包。"""
        if not self._is_open_10_pack_enabled():
            return False
        pack_hourglass_count = cast(int | None, self.state_get("pack_hourglass_count"))
        if pack_hourglass_count is None:
            return False
        return pack_hourglass_count >= OPEN_10_PACK_HOURGLASS_COST

    def _has_started_10_pack_this_task(self) -> bool:
        """判断本次任务是否已经发起过一次10包。"""
        return self._get_state_flag("ten_pack", "confirmed") or self._get_state_flag(
            "ten_pack", "completed"
        )

    def _has_completed_10_pack_this_task(self) -> bool:
        """判断本次任务是否已经完整处理完一次10包。"""
        return self._get_state_flag("ten_pack", "completed")

    def _should_exit_pack_flow_after_free_packs(self) -> bool:
        """免费包开完且不进入十包时，退出整条选包链路。"""
        return self._get_state_flag("pack_flow", "exit_after_paid")

    def _should_confirm_10_pack_modal(self) -> bool:
        """判断当前 modal 是否应该确认 10 包开封。"""
        return self._can_open_10_pack() and not self._has_started_10_pack_this_task()

    # ============================================================
    # 辅助方法
    # ============================================================

    def _get_target_series(self) -> Optional[str]:
        """根据 set_code 获取目标系列（A/B）"""
        target_pack = cast(dict[str, str] | None, self.state_get("target_pack"))
        if not target_pack:
            return None
        set_code = target_pack["set_code"]
        return set_code[0].upper() if set_code else None

    def _get_target_template_name(self) -> Optional[str]:
        """获取目标卡包的模板名称"""
        target_pack = cast(dict[str, str] | None, self.state_get("target_pack"))
        if not target_pack:
            return None
        from ptcgp_auto_v2.utils.pack_image_manager import PackImageManager

        manager = PackImageManager()
        return manager.get_template_name(target_pack["booster_name"])
