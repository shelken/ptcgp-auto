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
"""

import logging
import time
from datetime import datetime
from enum import Enum, auto
from typing import TYPE_CHECKING, Optional

from ptcgp_auto_v2.core.task_base import (
    ActionResult,
    ResetType,
    Task,
    TaskRegistry,
    TaskResult,
)
from ptcgp_auto_v2.locales import get_text_patterns
from ptcgp_auto_v2.utils.gesture import (
    is_text_visible,
    tap_text,
    tap_text_exact,
    tap_center,
    tap_box,
    tap_template,
    swipe_up,
    swipe,
    click_close,
    tap,
    quick_tap,
    tap_matched_element,
    tap_ok,
    clear_text,
)

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)

# 延迟导入 OpenPackTask（避免循环导入）
_open_pack_task = None


def _get_open_pack_task(adb, recognizer, page_detector):
    """获取 OpenPackTask 实例（延迟创建）"""
    global _open_pack_task
    if _open_pack_task is None:
        from ptcgp_auto_v2.tasks.open_pack import OpenPackTask

        _open_pack_task = OpenPackTask(adb, recognizer, page_detector)
    return _open_pack_task


# ============================================================
# 常量定义（基于 1080x1920 基准分辨率）
# ============================================================

# 昵称输入框 Y 坐标（基准 1080x1920）
INPUT_BOX_Y = 860

# 国家/地区按钮兜底点击位置（当 OCR 无法识别时使用）
# 位置：屏幕中央水平，Y 坐标 745（基于 1920 高度）
BASE_COUNTRY_BTN_Y = 745


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


# ============================================================
# 页面识别规则
# ============================================================


def _build_init_pages() -> list[dict]:
    """构建新账号初始化任务页面规则"""
    return [
        {
            "name": "init_select_country",
            "identifiers": get_text_patterns("init_select_country"),
            "priority": 99,
        },
        {
            "name": "init_terms_privacy",
            "identifiers": get_text_patterns("init_terms_privacy"),
            "priority": 99,
        },
        {
            "name": "init_data_use",
            "identifiers": get_text_patterns("init_data_use"),
            "priority": 98,
        },
        {
            "name": "init_create_save",
            "identifiers": get_text_patterns("init_create_save"),
            "priority": 99,
        },
        {
            "name": "init_account_link",
            "identifiers": get_text_patterns("init_account_link"),
            "priority": 99,
        },
        {
            "name": "init_set_nickname",
            "identifiers": get_text_patterns("init_set_nickname"),
            "priority": 99,
        },
        {
            "name": "init_nickname_input",
            "identifiers": get_text_patterns("init_nickname_title"),
            "exact_match": True,
            "priority": 99,
        },
        {
            "name": "init_confirm_settings",
            "identifiers": get_text_patterns("init_confirm_settings"),
            "priority": 99,
        },
        {
            "name": "init_select_pack",
            "identifiers": get_text_patterns("init_select_pack"),
            "priority": 99,
        },
        {
            "name": "init_decide",
            "identifiers": get_text_patterns("init_decide"),
            "exact_match": True,
            "priority": 99,
        },
        {
            "name": "init_swipe_open",
            "identifiers": get_text_patterns("init_swipe_open"),
            "priority": 99,
        },
        {
            "name": "init_next_step",
            "identifiers": get_text_patterns("init_next_step"),
            "exact_match": True,
            "priority": 99,
        },
        {
            "name": "init_open_pack",
            "identifiers": get_text_patterns("init_open_pack"),
            "exact_match": True,
            "priority": 99,
        },
        {
            "name": "init_enjoy",
            "identifiers": get_text_patterns("init_enjoy"),
            "priority": 99,
        },
        {
            "name": "init_tap_to_flip",
            "identifiers": get_text_patterns("init_tap_to_flip"),
            "priority": 99,
        },
        {
            "name": "init_select_favorite_card",
            "identifiers": get_text_patterns("init_select_favorite_card"),
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
            "name": "pack_opening_card",
            "identifiers": get_text_patterns("long_press"),
            "priority": 99,
        },
        {"name": "speed_up_button", "templates": ["btn_speed_up"], "priority": 99},
    ]


@TaskRegistry.register("init_account")
class InitAccountTask(Task):
    """
    新账号初始化任务

    自动完成新账号的完整初始化流程，采用状态机管理各阶段。
    此任务为一次性任务，完成后不会再次执行。
    """

    task_type = "init_account"
    reset_type = ResetType.ONCE
    max_iterations = 300
    max_unknown_pages = 30
    pages = _build_init_pages()

    # 可接受的国家/地区列表（匹配到任一即可）
    ALLOWED_COUNTRIES = ["香港", "台湾", "日本", "新加坡"]
    # 默认目标国家（向后兼容）
    TARGET_COUNTRY = "香港"
    # 目标昵称
    TARGET_NICKNAME = "skn"
    # 出生年份偏移（当前年份 - OFFSET）
    BIRTH_YEAR_OFFSET = 20
    # 出生月份
    BIRTH_MONTH = 2

    def __init__(self, adb, recognizer, page_detector):
        super().__init__(adb, recognizer, page_detector)
        self._phase = InitAccountPhase.INIT
        self._action_cache: dict[str, bool] = {}

    def _is_action_done(self, key: str) -> bool:
        """检查操作是否已完成"""
        return self._action_cache.get(key, False)

    def _mark_action_done(self, key: str):
        """标记操作已完成"""
        self._action_cache[key] = True

    def on_start(self):
        """任务开始前的初始化"""
        logger.info("开始新账号初始化任务")
        self._phase = InitAccountPhase.INIT

    def is_completed(self) -> bool:
        """判断任务是否已完成"""
        return self._phase == InitAccountPhase.COMPLETED

    def handle_page(self, page_name: str, page_info: dict) -> ActionResult:
        """处理识别到的页面"""
        logger.debug(f"处理页面: {page_name}, 当前阶段: {self._phase.name}")

        # 页面处理器映射
        handlers = {
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
            "init_swipe_open": self._handle_swipe_open,
            "init_next_step": lambda p: self._tap_text_exact(
                p, "init_next_step", "下一步"
            ),
            "init_open_pack": lambda p: self._tap_text_exact(
                p, "init_open_pack", "開封"
            ),
            "init_tap_to_flip": self._handle_tap_to_flip,
            "init_select_favorite_card": self._handle_select_favorite_card,
            "init_enjoy": self._handle_enjoy,
            "pack_opening_result": self._handle_pack_opening_result,
            "pack_card_register": self._handle_card_register,
            "pack_opening_card": self._handle_opening_card,
        }

        handler = handlers.get(page_name)
        if handler:
            return handler(page_info)

        logger.warning(f"未处理的页面: {page_name}")
        return ActionResult.ok(wait=1.0)

    def _handle_speed_up(self, page_info: dict) -> ActionResult:
        """处理快进按钮"""
        return tap_matched_element(self.adb, page_info, 0.1) or ActionResult.ok()

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
        tap_text_exact(
            self.adb, page_info.get("ocr_results", []), get_text_patterns("text_task")
        )
        return quick_tap(self.adb, wait=0.5)

    def on_complete(self, result: TaskResult):
        """任务完成后的处理"""
        logger.info(
            f"初始化任务完成，阶段: {self._phase.name}, "
            f"结果: {'成功' if result.success else '失败'}"
        )

    # ============================================================
    # 页面处理方法
    # ============================================================

    def _handle_select_country(self, page_info: dict) -> ActionResult:
        """
        处理选择国家/地区页面

        流程：
        1. 点击「國家/地區」打开列表
        2. 从上往下滑动查找 TARGET_COUNTRY
        3. 点击 TARGET_COUNTRY
        4. 点击「年」，上滑选择年份
        5. 点击「月」，点击 2
        6. 点击 OK
        """
        ocr_results = page_info.get("ocr_results", [])

        # 辅助函数：查找 OCR 中匹配的第一个允许国家
        def _find_allowed_country(ocr_results: list[dict]) -> str | None:
            for country in self.ALLOWED_COUNTRIES:
                if is_text_visible(ocr_results, [country]):
                    return country
            return None

        # 步骤 1: 检测是否已选择允许列表中的任一国家
        if not self._is_action_done("select_country_list_opened"):
            matched_country = _find_allowed_country(ocr_results)
            if matched_country:
                logger.info(
                    f"  -> 检测到允许的国家 {matched_country} 已选择，跳过国家选择"
                )
                self._mark_action_done("select_country_country_clicked")
                self._mark_action_done("select_country_list_opened")
            else:
                # 优先尝试 OCR 识别文字点击
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

                # 兜底方案：OCR 失败时直接点击固定坐标
                logger.info("  -> OCR 未识别到按钮，使用兜底坐标点击")
                tap_y = self.adb.scaled_y(BASE_COUNTRY_BTN_Y)
                result = tap(self.adb, self.adb.center_x(), tap_y, wait=1.0)
                self._mark_action_done("select_country_list_opened")
                return result

        # 步骤 2: 在列表中查找并点击允许的国家
        if not self._is_action_done("select_country_country_clicked"):
            matched_country = _find_allowed_country(ocr_results)
            if matched_country:
                logger.info(f"  -> 找到允许的国家 {matched_country}，点击选择")
                result = tap_text_exact(
                    self.adb, ocr_results, [matched_country], wait=0.5
                )
                if result:
                    self._mark_action_done("select_country_country_clicked")
                    return result
            else:
                logger.info("  -> 滑动查找目标国家")
                return swipe_up(self.adb, ratio=0.3, wait=2.0)

        # 步骤 3: 点击「年」打开年份选择列表
        if not self._is_action_done("select_country_year_clicked"):
            if is_text_visible(ocr_results, get_text_patterns("init_year_btn")):
                result = tap_text_exact(
                    self.adb, ocr_results, get_text_patterns("init_year_btn"), wait=1.0
                )
                if result:
                    logger.info("  -> 点击「年」打开年份选择")
                    self._mark_action_done("select_country_year_clicked")
                    return result

        # 步骤 4: 在年份列表中查找并选择目标年份（仅在已点击「年」后执行）
        if self._is_action_done(
            "select_country_year_clicked"
        ) and not self._is_action_done("select_country_year_selected"):
            target_year = str(datetime.now().year - self.BIRTH_YEAR_OFFSET)
            if is_text_visible(ocr_results, [target_year]):
                logger.info(f"  -> 找到年份 {target_year}，点击选择")
                result = tap_text_exact(self.adb, ocr_results, [target_year], wait=0.5)
                if result:
                    self._mark_action_done("select_country_year_selected")
                    return result
            else:
                logger.info("  -> 上滑查找目标年份")
                start_x = self.adb.scaled_x(300)
                start_y = self.adb.scaled_y(1400)
                end_y = self.adb.scaled_y(900)
                return swipe(
                    self.adb,
                    (start_x, end_y),
                    (start_x, start_y),
                    duration=300,
                    wait=1.0,
                )

        # 步骤 5: 点击「月」打开月份选择列表
        if not self._is_action_done("select_country_month_clicked"):
            if is_text_visible(ocr_results, get_text_patterns("init_month_btn")):
                result = tap_text_exact(
                    self.adb, ocr_results, get_text_patterns("init_month_btn"), wait=1.0
                )
                if result:
                    logger.info("  -> 点击「月」打开月份选择")
                    self._mark_action_done("select_country_month_clicked")
                    return result

        # 步骤 6: 在月份列表中点击「2」（仅在已点击「月」后执行）
        if self._is_action_done(
            "select_country_month_clicked"
        ) and not self._is_action_done("select_country_month_selected"):
            result = tap_text_exact(
                self.adb, ocr_results, get_text_patterns("init_month_2"), wait=0.5
            )
            if result:
                logger.info("  -> 选择月份 2")
                self._mark_action_done("select_country_month_selected")
                return result

        # 最后点击 OK 完成整个页面
        result = tap_ok(self.adb, ocr_results, wait=1.0)
        return result or ActionResult.ok(wait=1.0)

    def _handle_data_use(self, page_info: dict) -> ActionResult:
        """处理数据使用页面"""
        logger.debug(f"matched_text: {page_info.get('matched_text')}")
        matches = self.page_detector.find_all_templates(
            "icon_gray_yes", threshold=0.95, scale=0.72
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
        """
        处理条款与隐私页面

        流程：
        1. 点击「使用條款」
        2. 点击「隱私權政策」
        3. 点击所有 icon_gray_yes 模板直到消失
        4. 点击 OK
        """
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
        match = self.page_detector.find_template("icon_gray_yes", threshold=0.95)
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
        """
        处理设置昵称页面

        流程：
        1. 检测昵称是否已正确设置（精确匹配）
        2. 检测是否有异常提示（需要清空重输）
        3. 点击铅笔图标进入输入页面
        4. 点击输入框
        5. 输入昵称
        6. 点击 OK
        """
        ocr_results = page_info.get("ocr_results", [])
        screenshot, _ = self.page_detector.get_last_page_context()

        # 步骤 1: 精确检测目标昵称是否已设置成功
        if is_text_visible(ocr_results, [self.TARGET_NICKNAME], exact=True):
            logger.info(f"  -> 检测到昵称 {self.TARGET_NICKNAME} 已设置，点击 OK 完成")
            result = tap_ok(self.adb, ocr_results, wait=1.0)
            return result or ActionResult.ok(wait=1.0)

        # 步骤 2: 检测异常提示（如 "請勿使用本名"），需要清空重新输入
        if is_text_visible(ocr_results, get_text_patterns("init_nickname_warning")):
            logger.info("  -> 检测到昵称异常提示，清空重新输入")
            # 清空输入框并重新输入
            clear_text(
                self.adb,
                self.adb.center_x(),
                self.adb.scaled_y(INPUT_BOX_Y),
                max_chars=20,
            )
            logger.info(f"  -> 输入昵称: {self.TARGET_NICKNAME}")
            self.adb.device.send_keys(self.TARGET_NICKNAME)
            time.sleep(0.5)
            # 点击 OK 确认
            result = tap_ok(self.adb, ocr_results, wait=1.0)
            return result or ActionResult.ok(wait=1.0)

        # 步骤 3: 点击铅笔图标进入编辑
        match = self.page_detector.find_template_with_scale(
            "icon_pencil", screenshot=screenshot
        )
        if match:
            logger.info("  -> 点击铅笔图标编辑昵称")
            return tap_box(self.adb, match.box, wait=1.0)

        # 步骤 4: 点击输入框并输入昵称（首次输入）
        result = tap(self.adb, self.adb.center_x(), INPUT_BOX_Y, wait=0.5)
        if result:
            logger.info(f"  -> 点击输入框，输入昵称: {self.TARGET_NICKNAME}")
            self.adb.device.send_keys(self.TARGET_NICKNAME)
            time.sleep(0.5)

        # 步骤 5: 点击 OK
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

    def _handle_swipe_open(self, page_info: dict) -> ActionResult:
        """处理滑动开包引导页面"""
        logger.info("  -> 滑动开包")
        open_pack_task = _get_open_pack_task(
            self.adb, self.recognizer, self.page_detector
        )
        return open_pack_task._handle_opening_swipe(page_info)

    def _handle_tap_to_flip(self, page_info: dict) -> ActionResult:
        """处理翻开卡牌页面"""
        logger.info("  -> 快速点击翻开卡牌")
        return quick_tap(self.adb, wait=0.5)

    def _handle_select_favorite_card(self, page_info: dict) -> ActionResult:
        """处理选择喜欢的卡牌页面"""
        logger.info("  -> 选择喜欢的卡牌")
        tap_x = self.adb.center_x()
        tap_y = self.adb.scaled_y(740)
        return tap(self.adb, tap_x, tap_y, wait=1.0)

    def _handle_enjoy(self, page_info: dict) -> ActionResult:
        """处理完成页面"""
        logger.info("  -> 初始化完成，点击继续")
        self._phase = InitAccountPhase.COMPLETED
        return tap_center(self.adb, wait=2.0)

    def _handle_pack_opening_result(self, page_info: dict) -> ActionResult:
        """处理开包结果页面（复用 OpenPackTask）"""
        open_pack_task = _get_open_pack_task(
            self.adb, self.recognizer, self.page_detector
        )
        return open_pack_task._handle_pack_opening_result(page_info)

    def _handle_card_register(self, page_info: dict) -> ActionResult:
        """处理卡牌登录页面（复用 OpenPackTask）"""
        open_pack_task = _get_open_pack_task(
            self.adb, self.recognizer, self.page_detector
        )
        return open_pack_task._handle_card_register(page_info)

    def _handle_opening_card(self, page_info: dict) -> ActionResult:
        """处理卡牌展示页面（复用 OpenPackTask）"""
        open_pack_task = _get_open_pack_task(
            self.adb, self.recognizer, self.page_detector
        )
        return open_pack_task._handle_opening_card(page_info)
