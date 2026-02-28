# -*- coding: utf-8 -*-
"""
新账号初始化任务模块

采用状态机模式管理新账号的完整初始化流程，包括：
- 选择国家/地区
- 设置生日
- 同意条款与隐私政策
- 创建存档
- 设置昵称
- 选择初始卡包
- 开包引导流程

继承 PackOpeningTaskBase，教程开包接入统一识别与开包记录流程，pack_type 设为 init_tutorial。
"""

import logging
import time
from datetime import datetime
from enum import Enum, auto
from typing import TYPE_CHECKING

from ptcgp_auto_v2.core.task_base import (
    ActionResult,
    ResetType,
    TaskRegistry,
    TaskResult,
)
from ptcgp_auto_v2.locales import get_text_patterns
from ptcgp_auto_v2.tasks.pack_opening_task_base import (
    PackOpeningTaskBase,
    build_pack_opening_pages,
)
from ptcgp_auto_v2.tasks.utils.card_pick import tap_favorite_card
from ptcgp_auto_v2.utils.gesture import (
    click_close,
    input_text,
    is_text_visible,
    quick_tap,
    scroll_points,
    swipe,
    tap,
    tap_box,
    tap_center,
    tap_matched_element,
    tap_ok,
    tap_template,
    tap_text,
    tap_text_exact,
)

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)


# ============================================================
# 页面识别规则（合并通用开包页面）
# ============================================================


def _build_init_pages() -> list[dict]:
    """构建新账号初始化任务页面规则（合并通用开包页面）"""
    task_specific_pages = [
        # 選擇國家 / 請選擇您居住的國家
        {
            "name": "init_select_country",
            "identifiers": get_text_patterns("init_select_country"),
            "priority": 99,
        },
        # 使用條款 / 隱私權政策
        {
            "name": "init_terms_privacy",
            "identifiers": get_text_patterns("init_terms_privacy"),
            "priority": 99,
        },
        # 關於資料使用
        {
            "name": "init_data_use",
            "identifiers": get_text_patterns("init_data_use"),
            "priority": 98,
        },
        # 建立儲存資料
        {
            "name": "init_create_save",
            "identifiers": get_text_patterns("init_create_save"),
            "priority": 99,
        },
        # 帳號連結
        {
            "name": "init_account_link",
            "identifiers": get_text_patterns("init_account_link"),
            "priority": 99,
        },
        # 請設定頭像和玩家名稱
        {
            "name": "init_set_nickname",
            "identifiers": get_text_patterns("init_set_nickname"),
            "priority": 99,
        },
        # 玩家名稱
        {
            "name": "init_nickname_input",
            "identifiers": get_text_patterns("init_nickname_title"),
            "exact_match": True,
            "priority": 99,
        },
        # 確定要使用此設定嗎
        {
            "name": "init_confirm_settings",
            "identifiers": get_text_patterns("init_confirm_settings"),
            "priority": 99,
        },
        # 請選擇喜歡的擴充包
        {
            "name": "init_select_pack",
            "identifiers": get_text_patterns("init_select_pack"),
            "priority": 99,
        },
        # 決定
        {
            "name": "init_decide",
            "identifiers": get_text_patterns("init_decide"),
            "exact_match": True,
            "priority": 99,
        },
        # 下一步
        {
            "name": "init_next_step",
            "identifiers": get_text_patterns("init_next_step"),
            "exact_match": True,
            "priority": 99,
        },
        # 開封
        {
            "name": "init_open_pack",
            "identifiers": get_text_patterns("init_open_pack"),
            "exact_match": True,
            "priority": 99,
        },
        # 請好好享受 / 隨意遊玩
        {
            "name": "init_enjoy",
            "identifiers": get_text_patterns("init_enjoy"),
            "priority": 99,
        },
        # 商店 / 得卡挑戰
        {
            "name": "game_home_main",
            "identifiers": get_text_patterns("game_home_main"),
            "match_all": True,
            "priority": 90,
        },
        # 點擊來翻開卡牌吧
        {
            "name": "init_tap_to_flip",
            "identifiers": get_text_patterns("init_tap_to_flip"),
            "priority": 99,
        },
        # 選1張喜歡的卡牌吧
        {
            "name": "init_select_favorite_card",
            "identifiers": get_text_patterns("init_select_favorite_card"),
            "priority": 99,
        },
    ]
    return task_specific_pages + build_pack_opening_pages()


# ============================================================
# 常量定义（基于 1080x1920 基准分辨率）
# ============================================================

# 昵称输入框 Y 坐标（基准 1080x1920）
INPUT_BOX_Y = 860

# 国家/地区按钮兜底点击位置（当 OCR 无法识别时使用）
BASE_COUNTRY_BTN_Y = 745

# 国家/地区列表滚动距离（基于 1920 高度）
BASE_COUNTRY_SCROLL_DISTANCE_Y = 576  # 1920 * 0.30

# 未知页面兜底点击点位（基于 1080x1920）
BASE_UNKNOWN_TOP_TAP_Y = 10
BASE_UNKNOWN_TASK_TAP_X = 960
BASE_UNKNOWN_TASK_TAP_Y = 1740

# 主页兜底完成阈值：当已完成「选择喜欢的卡牌」后，连续识别到主页达到该次数即判定完成
HOME_FALLBACK_THRESHOLD = 8


class InitAccountPhase(Enum):
    """新账号初始化任务阶段（仅用于页面间流转）"""

    INIT = auto()  # 初始化
    SELECT_COUNTRY = auto()  # 选择国家/地区
    TERMS_PRIVACY = auto()  # 条款与隐私
    CREATE_SAVE = auto()  # 创建存档
    ACCOUNT_LINK = auto()  # 账号链接
    SET_NICKNAME = auto()  # 设置昵称
    SELECT_PACK = auto()  # 选择初始卡包
    SWIPE_OPEN = auto()  # 滑动开包引导
    COMPLETED = auto()  # 初始化完成


@TaskRegistry.register("init_account")
class InitAccountTask(PackOpeningTaskBase):
    """
    新账号初始化任务

    自动完成新账号的完整初始化流程，采用状态机管理各阶段。
    此任务为一次性任务，完成后不会再次执行。
    继承 PackOpeningTaskBase，教程开包接入统一识别与开包记录流程。
    """

    task_type = "init_account"
    reset_type = ResetType.ONCE
    max_iterations = 300
    max_unknown_pages = 30
    pages = _build_init_pages()

    # 可接受的国家/地区列表（匹配到任一即可）
    ALLOWED_COUNTRIES = ["香港", "台湾", "日本", "新加坡", "美國"]
    # 默认目标国家（向后兼容）
    TARGET_COUNTRY = "香港"
    # 昵称前缀
    NICKNAME_PREFIX = "skn"
    # 出生年份偏移（当前年份 - OFFSET）
    BIRTH_YEAR_OFFSET = 20
    # 出生月份
    BIRTH_MONTH = 2

    def __init__(self, adb, recognizer, page_detector):
        super().__init__(adb, recognizer, page_detector)
        self._phase = InitAccountPhase.INIT
        self._action_cache: dict[str, bool | int] = {}

    # ============================================================
    # 扩展点实现（PackOpeningTaskBase 要求）
    # ============================================================

    def get_pack_record_type(self) -> str:
        """返回 pack 记录类型：教程初始包"""
        return "init_tutorial"

    def get_rare_card_notify_message(self) -> str:
        """返回稀有卡通知消息：新手初始化"""
        return "新手开包获得稀有卡牌"

    def should_prepare_pack_resources(self) -> bool:
        """初始化任务不需要准备卡包图片资源"""
        return False

    # ============================================================
    # 任务生命周期
    # ============================================================

    def on_start(self):
        """任务开始前的初始化"""
        logger.info("开始新账号初始化任务")
        self._phase = InitAccountPhase.INIT

        # 初始化基类的仓储和数据
        self._init_repositories()
        self._action_cache.clear()
        self._packs_opened_count = 0
        self._result_recognized = False

    def is_completed(self) -> bool:
        """判断任务是否已完成"""
        return self._phase == InitAccountPhase.COMPLETED

    def handle_page(self, page_name: str, page_info: dict) -> ActionResult:
        """处理识别到的页面"""
        logger.debug(f"处理页面: {page_name}, 当前阶段: {self._phase.name}")

        # 仅在"连续主页"场景累计计数；一旦离开主页立即重置
        if page_name != "game_home_main":
            self._action_cache.pop("home_consecutive_count", None)

        # 初始化任务特定页面处理器（优先于通用处理器）
        specific_handlers = {
            "speed_up_button": self._handle_speed_up,
            "init_select_country": self._handle_select_country,
            "init_terms_privacy": self._handle_terms_privacy,
            "init_data_use": self._handle_data_use,
            "init_create_save": self._handle_create_save,
            "init_account_link": self._handle_account_link,
            "init_set_nickname": self._handle_set_nickname,
            "init_nickname_input": self._handle_set_nickname,
            "init_confirm_settings": self._handle_confirm_settings,
            "init_select_pack": self._handle_select_pack,
            "init_decide": lambda p: self._tap_text_exact(p, "init_decide", "決定"),
            "init_next_step": lambda p: self._tap_text_exact(
                p, "init_next_step", "下一步"
            ),
            "init_open_pack": lambda p: self._tap_text_exact(
                p, "init_open_pack", "開封"
            ),
            "init_tap_to_flip": self._handle_tap_to_flip,
            "init_select_favorite_card": self._handle_select_favorite_card,
            "init_enjoy": self._handle_enjoy,
            "game_home_main": self._handle_game_home_main,
        }
        # 合并：特定处理器优先覆盖通用处理器
        handlers = {**self.build_pack_opening_handlers(), **specific_handlers}

        handler = handlers.get(page_name)
        if handler:
            return handler(page_info)

        logger.warning(f"未处理的页面: {page_name}")
        return ActionResult.ok(wait=1.0)

    def _handle_speed_up(self, page_info: dict) -> ActionResult:
        """处理快进按钮"""
        return tap_matched_element(self.adb, page_info, 0.5) or ActionResult.ok(
            wait=0.5
        )

    def _tap_text_exact(
        self, page_info: dict, pattern_key: str, log_msg: str
    ) -> ActionResult:
        """通用精确点击文本处理器"""
        ocr_results = page_info.get("ocr_results", [])
        result = tap_text_exact(
            self.adb, ocr_results, get_text_patterns(pattern_key), wait=1.0
        )
        if result:
            logger.info(f"  -> 点击「{log_msg}」")
        return result or ActionResult.ok(wait=1.0)

    def handle_unknown_page(self, page_info) -> ActionResult:
        """处理未知页面"""
        logger.debug("未知页面，点击屏幕中心兜底")
        return self._quick_tap_home_like_fallback()

    def _quick_tap_home_like_fallback(self) -> ActionResult:
        """主页/未知页统一兜底点击逻辑。"""
        return quick_tap(
            self.adb,
            tap_points=[
                (self.adb.center_x(), self.adb.scaled_y(BASE_UNKNOWN_TOP_TAP_Y)),
                (self.adb.center_x(), self.adb.center_y()),
                (
                    self.adb.scaled_x(BASE_UNKNOWN_TASK_TAP_X),
                    self.adb.scaled_y(BASE_UNKNOWN_TASK_TAP_Y),
                ),
            ],
            times=1,
            wait=0.5,
        )

    def on_complete(self, result: TaskResult):
        """任务完成后的处理"""
        logger.info(
            f"初始化任务完成，阶段: {self._phase.name}, "
            f"结果: {'成功' if result.success else '失败'}"
        )

        # 成功后自动分配 base 计划
        if result.success and self.account:
            self._assign_base_plan()

    def _assign_base_plan(self):
        """为完成的账号分配 base 计划"""
        from ptcgp_auto_v2.db.repositories import AccountRepository, TaskPlanRepository

        try:
            plan_repo = TaskPlanRepository()
            account_repo = AccountRepository()

            base_plan = plan_repo.get_by_name("base")
            if base_plan and self.account.id:
                account_repo.add_secondary_plan(
                    account_id=self.account.id, plan_id=base_plan.id, priority=0
                )
                logger.info(
                    f"账号 {self.account.nickname or self.account.game_id} 已自动分配 base 计划"
                )
        except Exception as e:
            logger.warning(f"分配 base 计划失败: {e}")

    # ============================================================
    # 页面处理方法
    # ============================================================

    def _find_allowed_country(
        self, ocr_results: list[dict], exact: bool = False
    ) -> str | None:
        """在 OCR 结果中查找第一个允许国家。"""
        for country in self.ALLOWED_COUNTRIES:
            if is_text_visible(ocr_results, [country], exact=exact):
                return country
        return None

    def _is_country_list_overlay(self, ocr_results: list[dict]) -> bool:
        """判断当前是否处于国家列表弹层。"""
        return is_text_visible(
            ocr_results,
            get_text_patterns("init_country_list_close"),
            exact=True,
        )

    def _swipe_country_list(self) -> ActionResult:
        """在国家列表中上滑查找目标国家。"""
        start, end = scroll_points(
            self.adb,
            base_distance_y=BASE_COUNTRY_SCROLL_DISTANCE_Y,
            direction="up",
        )
        return swipe(self.adb, start, end, wait=2.0)

    def _handle_country_list_overlay(self, ocr_results: list[dict]) -> ActionResult:
        """处理国家列表弹层：循环执行"点国家 + 点OK"，找不到则滑动。"""
        matched_country = self._find_allowed_country(ocr_results, exact=True)
        if matched_country:
            logger.info(f"  -> 国家列表弹层：点击允许国家 {matched_country}")
            tap_text_exact(self.adb, ocr_results, [matched_country], wait=0.2)
            ok_result = tap_ok(self.adb, ocr_results, wait=1.0)
            return ok_result or ActionResult.ok(wait=1.0)

        logger.info("  -> 国家列表弹层：未找到允许国家，继续滑动查找")
        return self._swipe_country_list()

    def _open_country_list_if_needed(
        self, ocr_results: list[dict], is_country_form_ready: bool
    ) -> ActionResult | None:
        """在主表单中按需打开国家列表。"""
        if self._is_action_done("select_country_list_opened") or is_country_form_ready:
            return None

        result = tap_text_exact(
            self.adb,
            ocr_results,
            get_text_patterns("init_country_btn"),
            wait=1.0,
        )
        if result:
            logger.info("  -> 点击「國家/地區」打开列表")
            self._mark_action_done("select_country_list_opened")
            return result

        logger.info("  -> OCR 未识别到按钮，使用兜底坐标点击")
        tap_y = self.adb.scaled_y(BASE_COUNTRY_BTN_Y)
        result = tap(self.adb, self.adb.center_x(), tap_y, wait=1.0)
        self._mark_action_done("select_country_list_opened")
        return result

    def _select_country_if_needed(
        self, ocr_results: list[dict], is_country_form_ready: bool
    ) -> ActionResult | None:
        """在主表单阶段按需确认国家已选择。"""
        if self._is_action_done("select_country_country_clicked"):
            return None

        if is_country_form_ready:
            self._mark_action_done("select_country_country_clicked")
            return None

        matched_country = self._find_allowed_country(ocr_results)
        if matched_country:
            logger.info(f"  -> 找到允许的国家 {matched_country}，点击选择")
            result = tap_text_exact(self.adb, ocr_results, [matched_country], wait=0.5)
            if result:
                self._mark_action_done("select_country_country_clicked")
                return result
            return None

        logger.info("  -> 滑动查找目标国家")
        return self._swipe_country_list()

    def _select_birth_year_if_needed(
        self, ocr_results: list[dict]
    ) -> ActionResult | None:
        """按需选择出生年份。"""
        if not self._is_action_done("select_country_year_clicked"):
            if is_text_visible(ocr_results, get_text_patterns("init_year_btn")):
                result = tap_text_exact(
                    self.adb,
                    ocr_results,
                    get_text_patterns("init_year_btn"),
                    wait=1.0,
                )
                if result:
                    logger.info("  -> 点击「年」打开年份选择")
                    self._mark_action_done("select_country_year_clicked")
                    return result
            return None

        if self._is_action_done("select_country_year_selected"):
            return None

        target_year = str(datetime.now().year - self.BIRTH_YEAR_OFFSET)
        if is_text_visible(ocr_results, [target_year]):
            logger.info(f"  -> 找到年份 {target_year}，点击选择")
            result = tap_text_exact(self.adb, ocr_results, [target_year], wait=0.5)
            if result:
                self._mark_action_done("select_country_year_selected")
                return result
            return None

        logger.info("  -> 上滑查找目标年份")
        start_x = self.adb.scaled_x(300)
        start_y = self.adb.scaled_y(1400)
        end_y = self.adb.scaled_y(900)
        return swipe(
            self.adb,
            (start_x, end_y),
            (start_x, start_y),
            wait=1.0,
        )

    def _select_birth_month_if_needed(
        self, ocr_results: list[dict]
    ) -> ActionResult | None:
        """按需选择出生月份。"""
        if not self._is_action_done("select_country_month_clicked"):
            if is_text_visible(ocr_results, get_text_patterns("init_month_btn")):
                result = tap_text_exact(
                    self.adb,
                    ocr_results,
                    get_text_patterns("init_month_btn"),
                    wait=1.0,
                )
                if result:
                    logger.info("  -> 点击「月」打开月份选择")
                    self._mark_action_done("select_country_month_clicked")
                    return result
            return None

        if self._is_action_done("select_country_month_selected"):
            return None

        result = tap_text_exact(
            self.adb,
            ocr_results,
            get_text_patterns("init_month_2"),
            wait=0.5,
        )
        if result:
            logger.info("  -> 选择月份 2")
            self._mark_action_done("select_country_month_selected")
            return result
        return None

    def _handle_select_country(self, page_info: dict) -> ActionResult:
        """处理选择国家/地区页面"""
        ocr_results = page_info.get("ocr_results", [])

        if self._is_country_list_overlay(ocr_results):
            return self._handle_country_list_overlay(ocr_results)

        has_selected_country = (
            self._find_allowed_country(ocr_results, exact=True) is not None
        )
        is_country_form_ready = has_selected_country

        for step in (
            lambda: self._open_country_list_if_needed(
                ocr_results, is_country_form_ready
            ),
            lambda: self._select_country_if_needed(ocr_results, is_country_form_ready),
            lambda: self._select_birth_year_if_needed(ocr_results),
            lambda: self._select_birth_month_if_needed(ocr_results),
        ):
            result = step()
            if result:
                return result

        result = tap_ok(self.adb, ocr_results, wait=1.0)
        return result or ActionResult.ok(wait=1.0)

    def _handle_data_use(self, page_info: dict) -> ActionResult:
        """处理数据使用页面"""
        logger.debug(f"matched_text: {page_info.get('matched_text')}")
        matches = self.page_detector.find_all_templates(
            "icon_gray_yes", threshold=0.90, scale=0.72
        )
        if matches:
            for match in matches:
                if match.box[0] < self.adb.center_x():
                    logger.debug(
                        f"  -> 跳过勾选图标位置: {match.box[0]} x {match.box[1]}"
                    )
                    continue
                logger.debug(f"  -> 点击勾选图标位置: {match.box[0]} x {match.box[1]}")
                tap_box(self.adb, match.box, wait=0)

        ocr_results = page_info.get("ocr_results", [])
        ok_result = tap_ok(self.adb, ocr_results, wait=1.0)
        if ok_result:
            return ok_result
        return ActionResult.ok()

    def _handle_terms_privacy(self, page_info: dict) -> ActionResult:
        """处理条款与隐私页面"""
        ocr_results = page_info.get("ocr_results", [])
        screenshot, _ = self.page_detector.get_last_page_context()

        # 看到x就点掉
        click_close(
            self.adb, self.page_detector, ocr_results, get_text_patterns("text_x")
        )
        tap_template(
            self.adb, self.page_detector, template_name="btn_back", threshold=0.95
        )

        # 步骤 1: 点击「使用條款」
        if not self._is_action_done("terms_privacy_terms_clicked"):
            result = tap_text_exact(
                self.adb, ocr_results, get_text_patterns("init_terms_btn"), wait=3
            )
            if result:
                logger.info("  -> 点击「使用條款」")
                self._mark_action_done("terms_privacy_terms_clicked")
                return result

        # 步骤 2: 点击「隱私權政策」
        if not self._is_action_done("terms_privacy_privacy_clicked"):
            result = tap_text_exact(
                self.adb, ocr_results, get_text_patterns("init_privacy_btn"), wait=3
            )
            if result:
                logger.info("  -> 点击「隱私權政策」")
                self._mark_action_done("terms_privacy_privacy_clicked")
                return result

        # 步骤 3: 点击所有灰色勾选图标直到消失
        match = self.page_detector.find_template("icon_gray_yes", threshold=0.89)
        if match:
            logger.info("  -> 点击灰色勾选图标")
            return tap_box(self.adb, match, wait=0.1)

        # 步骤 4: 点击 OK 完成页面
        result = tap_ok(self.adb, ocr_results, wait=0.5)
        if result:
            logger.info("  -> 点击 OK 完成条款与隐私页面")
            return result
        return ActionResult.ok(wait=1.0)

    def _handle_create_save(self, page_info: dict) -> ActionResult:
        """处理创建存档页面"""
        ocr_results = page_info.get("ocr_results", [])
        result = tap_text(
            self.adb,
            ocr_results,
            get_text_patterns("init_start_from_scratch"),
            exact=True,
            wait=1.0,
        )
        if result:
            logger.info("  -> 点击「從頭開始」")
        return result or ActionResult.ok(wait=1.0)

    def _handle_account_link(self, page_info: dict) -> ActionResult:
        """处理账号链接页面"""
        ocr_results = page_info.get("ocr_results", [])
        result = tap_text(
            self.adb,
            ocr_results,
            get_text_patterns("init_skip_link"),
            exact=True,
            wait=1.0,
        )
        if result:
            logger.info("  -> 点击「現在不連結」跳过账号链接")
        return result or ActionResult.ok(wait=1.0)

    def _handle_set_nickname(self, page_info: dict) -> ActionResult:
        """处理设置昵称页面"""
        ocr_results = page_info.get("ocr_results", [])
        screenshot, _ = self.page_detector.get_last_page_context()

        target_nickname = self._get_target_nickname()

        # 步骤 1: 精确检测目标昵称是否已设置成功
        if is_text_visible(ocr_results, [target_nickname], exact=True):
            logger.info(f"  -> 检测到昵称 {target_nickname} 已设置，点击 OK 完成")
            result = tap_ok(self.adb, ocr_results, wait=1.0)
            return result or ActionResult.ok(wait=1.0)

        # 步骤 2: 点击铅笔图标进入编辑
        match = self.page_detector.find_template_with_scale(
            "icon_pencil", screenshot=screenshot
        )
        if match:
            logger.info("  -> 点击铅笔图标编辑昵称")
            return tap_box(self.adb, match.box, wait=1.0)

        # 步骤 3: 点击输入框并输入昵称（首次输入）
        result = tap(
            self.adb, self.adb.center_x(), self.adb.scaled_y(INPUT_BOX_Y), wait=1.0
        )
        if result:
            logger.info(f"  -> 点击输入框，输入昵称: {target_nickname}")
            time.sleep(1.0)
            input_text(self.adb, target_nickname, wait=0.5)
            time.sleep(0.5)

        # 步骤 4: 点击 OK
        result = tap_ok(self.adb, ocr_results, wait=1.0)
        return result or ActionResult.ok(wait=1.0)

    def _handle_confirm_settings(self, page_info: dict) -> ActionResult:
        """处理确认设置页面"""
        ocr_results = page_info.get("ocr_results", [])
        result = tap_ok(self.adb, ocr_results, wait=1.0)
        if result:
            logger.info("  -> 确认设置")
        return result or ActionResult.ok(wait=1.0)

    def _handle_select_pack(self, page_info: dict) -> ActionResult:
        """处理选择初始卡包页面"""
        logger.info("  -> 选择初始卡包")
        return tap_center(self.adb, wait=1.0)

    def _handle_tap_to_flip(self, page_info: dict) -> ActionResult:
        """处理翻开卡牌页面"""
        logger.info("  -> 快速点击翻开卡牌")
        return quick_tap(self.adb)

    def _handle_select_favorite_card(self, page_info: dict) -> ActionResult:
        """处理选择喜欢的卡牌页面"""
        logger.info("  -> 选择喜欢的卡牌")
        result = tap_favorite_card(self.adb, wait=1.0)
        if result and result.success:
            self._mark_action_done("after_favorite_card")
        return result

    def _handle_enjoy(self, page_info: dict) -> ActionResult:
        """处理完成页面"""
        logger.info("  -> 初始化完成，点击继续")
        self._phase = InitAccountPhase.COMPLETED
        return tap_center(self.adb, wait=2.0)

    def _handle_game_home_main(self, page_info: dict) -> ActionResult:
        """处理游戏主页兜底：仅在后期里程碑达成后，连续主页超时才判定完成。"""
        tap_result = self._quick_tap_home_like_fallback()

        if not self._is_action_done("after_favorite_card"):
            logger.debug("  -> 已在主页，先点击推进提示；未到最终引导阶段，继续等待")
            return tap_result or ActionResult.ok(wait=1.0)

        home_count = int(self._action_cache.get("home_consecutive_count", 0)) + 1
        self._action_cache["home_consecutive_count"] = home_count

        if home_count >= HOME_FALLBACK_THRESHOLD:
            logger.warning(
                "  -> 已完成选喜欢卡牌且连续主页达到阈值，触发初始化完成兜底"
            )
            self._phase = InitAccountPhase.COMPLETED
            return tap_result or ActionResult.ok(wait=0.5)

        logger.info(
            f"  -> 已完成选喜欢卡牌，主页兜底计数 {home_count}/{HOME_FALLBACK_THRESHOLD}"
        )
        return tap_result or ActionResult.ok(wait=0.5)

    # ============================================================
    # 辅助方法
    # ============================================================

    def _get_target_nickname(self) -> str:
        """获取目标昵称，格式为 前缀 + 账号ID（如果没有账号则只有前缀）"""
        if self.account and self.account.id:
            return f"{self.NICKNAME_PREFIX}{self.account.id}"
        return self.NICKNAME_PREFIX

    def _is_action_done(self, key: str) -> bool:
        """检查操作是否已完成"""
        return bool(self._action_cache.get(key, False))

    def _mark_action_done(self, key: str):
        """标记操作已完成"""
        self._action_cache[key] = True
