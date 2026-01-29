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

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)

# ============================================================
# 常量定义（基于 1080x1920 基准分辨率的像素值）
# 使用时通过 adb.scaled_x/scaled_y 缩放到当前分辨率
# ============================================================

# 国家/地区选择按钮位置（屏幕中央偏下）
# 基于 1080x1920 分辨率，"國家/地區" 按钮大约在 y=1000 位置
BASE_COUNTRY_SELECT_Y = 1000

# 年份选择列表中的年份项位置（基于滚动选择器）
BASE_YEAR_ITEM_Y = 960  # 列表中央位置

# 月份选择位置
BASE_MONTH_ITEM_Y = 960

# 昵称输入框位置（屏幕中央）
BASE_NICKNAME_INPUT_Y = 960

# 卡包选择位置（三个卡包横向排列，选择中间或第一个）
BASE_PACK_SELECT_X = 540  # 屏幕中央
BASE_PACK_SELECT_Y = 1200

# 滑动开包起始和结束坐标（横向滑动）
BASE_SWIPE_START_X = 200
BASE_SWIPE_END_X = 880
BASE_SWIPE_Y = 1400


class InitAccountPhase(Enum):
    """新账号初始化任务阶段"""

    INIT = auto()  # 初始化
    SELECT_COUNTRY = auto()  # 选择国家/地区
    SET_BIRTHDAY = auto()  # 设置生日
    TERMS_PRIVACY = auto()  # 条款与隐私
    CREATE_SAVE = auto()  # 创建存档
    ACCOUNT_LINK = auto()  # 账号链接
    SET_NICKNAME = auto()  # 设置昵称
    SELECT_PACK = auto()  # 选择初始卡包
    SWIPE_OPEN = auto()  # 滑动开包引导
    MISSION_GUIDE = auto()  # 任务引导
    COMPLETED = auto()  # 初始化完成


from ptcgp_auto_v2.utils.gesture import (
    tap_text,
    tap_center,
    swipe,
    tap_box,
    center_point,
    tap_template,
    tap_template_with_scale,
)


def _get_patterns(key: str) -> list[str]:
    """获取指定配置的文本列表"""
    return get_text_patterns(key)


# ============================================================
# 页面识别规则
# 注意：priority 数值越小优先级越高
# ============================================================
def _build_init_pages() -> list[dict]:
    """构建新账号初始化任务页面规则"""
    return [
        {
            "name": "init_select_country",
            "identifiers": _get_patterns("init_select_country"),
            "priority": 99,
        },
        {
            "name": "init_terms_privacy",
            "identifiers": _get_patterns("init_terms_privacy"),
            "priority": 99,
        },
        {
            "name": "init_create_save",
            "identifiers": _get_patterns("init_create_save"),
            "priority": 99,
        },
        {
            "name": "init_account_link",
            "identifiers": _get_patterns("init_account_link"),
            "priority": 99,
        },
        {
            "name": "init_set_nickname",
            "identifiers": _get_patterns("init_set_nickname"),
            "priority": 99,
        },
        {
            "name": "init_nickname_input",
            "identifiers": _get_patterns("init_nickname_title"),
            "priority": 99,
        },
        {
            "name": "init_confirm_settings",
            "identifiers": _get_patterns("init_confirm_settings"),
            "priority": 99,
        },
        {
            "name": "init_select_pack",
            "identifiers": _get_patterns("init_select_pack"),
            "priority": 99,
        },
        {
            "name": "init_swipe_open",
            "identifiers": _get_patterns("init_swipe_open"),
            "priority": 99,
        },
        {
            "name": "init_next_step",
            "identifiers": _get_patterns("init_next_step"),
            "priority": 99,
        },
        {
            "name": "init_mission",
            "identifiers": _get_patterns("init_mission"),
            "priority": 99,
        },
        {
            "name": "init_enjoy",
            "identifiers": _get_patterns("init_enjoy"),
            "priority": 99,
        },
        # 复用开包任务的相关页面
        {
            "name": "pack_opening_result",
            "identifiers": _get_patterns("pack_opening_result"),
            "priority": 99,
        },
        {
            "name": "pack_card_register",
            "identifiers": _get_patterns("pack_card_register"),
            "priority": 99,
        },
        {
            "name": "pack_opening_card",
            "identifiers": _get_patterns("long_press"),
            "priority": 99,
        },
        # 通用页面
        {
            "name": "game_home_main",
            "match_all": True,
            "identifiers": _get_patterns("game_home_main"),
            "priority": 100,  # 优先级较低，避免干扰初始化流程
        },
    ]


@TaskRegistry.register("init_account")
class InitAccountTask(Task):
    """
    新账号初始化任务

    自动完成新账号的完整初始化流程，采用状态机管理各阶段。
    此任务为一次性任务，完成后不会再次执行。
    """

    task_type = "init_account"
    reset_type = ResetType.ONCE  # 一次性任务
    max_iterations = 200
    max_unknown_pages = 30
    pages = _build_init_pages()

    # 目标国家/地区
    TARGET_COUNTRY = "台灣"
    # 目标昵称
    TARGET_NICKNAME = "skn"
    # 出生年份（当前年份-20）
    BIRTH_YEAR_OFFSET = 20
    # 出生月份
    BIRTH_MONTH = 2

    def __init__(self, adb, recognizer, page_detector):
        super().__init__(adb, recognizer, page_detector)

        # 核心状态机
        self._phase = InitAccountPhase.INIT
        self._country_selected = False  # 是否已选择国家
        self._birthday_set = False  # 是否已设置生日
        self._terms_accepted = False  # 是否已同意条款
        self._save_created = False  # 是否已创建存档
        self._nickname_set = False  # 是否已设置昵称
        self._pack_selected = False  # 是否已选择卡包
        self._pack_opened = False  # 是否已完成开包引导

        # 条款页面处理状态
        self._terms_clicked = False  # 是否已点击使用条款
        self._privacy_clicked = False  # 是否已点击隐私政策
        self._gray_yes_clicked = False  # 是否已点击灰色勾选

    def on_start(self):
        """任务开始前的初始化"""
        logger.info("开始新账号初始化任务")
        self._phase = InitAccountPhase.INIT

    def is_completed(self) -> bool:
        """
        判断任务是否已完成

        结束条件：
        - 初始化流程全部完成（COMPLETED）
        - 或者已经进入游戏主页（说明初始化已完成）
        """
        return self._phase == InitAccountPhase.COMPLETED

    def handle_page(self, page_name: str, page_info: dict) -> ActionResult:
        """
        处理识别到的页面

        根据当前页面执行相应动作，并更新状态机阶段。
        """
        logger.debug(f"处理页面: {page_name}, 当前阶段: {self._phase.name}")

        # 选择国家/地区页面
        if page_name == "init_select_country":
            self._phase = InitAccountPhase.SELECT_COUNTRY
            return self._handle_select_country(page_info)

        # 条款与隐私页面
        if page_name == "init_terms_privacy":
            self._phase = InitAccountPhase.TERMS_PRIVACY
            return self._handle_terms_privacy(page_info)

        # 创建存档页面
        if page_name == "init_create_save":
            self._phase = InitAccountPhase.CREATE_SAVE
            return self._handle_create_save(page_info)

        # 账号链接页面
        if page_name == "init_account_link":
            self._phase = InitAccountPhase.ACCOUNT_LINK
            return self._handle_account_link(page_info)

        # 设置昵称页面
        if page_name == "init_set_nickname":
            self._phase = InitAccountPhase.SET_NICKNAME
            return self._handle_set_nickname(page_info)

        # 昵称输入页面
        if page_name == "init_nickname_input":
            return self._handle_nickname_input(page_info)

        # 确认设置页面
        if page_name == "init_confirm_settings":
            return self._handle_confirm_settings(page_info)

        # 选择卡包页面
        if page_name == "init_select_pack":
            self._phase = InitAccountPhase.SELECT_PACK
            return self._handle_select_pack(page_info)

        # 滑动开包引导页面
        if page_name == "init_swipe_open":
            self._phase = InitAccountPhase.SWIPE_OPEN
            return self._handle_swipe_open(page_info)

        # 下一步按钮页面
        if page_name == "init_next_step":
            return self._handle_next_step(page_info)

        # 任务引导页面
        if page_name == "init_mission":
            self._phase = InitAccountPhase.MISSION_GUIDE
            return self._handle_mission(page_info)

        # 完成页面
        if page_name == "init_enjoy":
            return self._handle_enjoy(page_info)

        # 开包结果页面（复用开包逻辑）
        if page_name == "pack_opening_result":
            return self._handle_pack_opening_result(page_info)

        # 卡牌登录页面（复用开包逻辑）
        if page_name == "pack_card_register":
            return self._handle_card_register(page_info)

        # 长按跳过卡牌（复用开包逻辑）
        if page_name == "pack_opening_card":
            return self._handle_opening_card(page_info)

        # 游戏主页（说明初始化已完成）
        if page_name == "game_home_main":
            logger.info("检测到游戏主页，初始化流程已完成")
            self._phase = InitAccountPhase.COMPLETED
            return ActionResult.ok(wait=1.0)

        # 其他页面
        logger.warning(f"未处理的页面: {page_name}")
        return ActionResult.ok(wait=1.0)

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
        1. 点击"國家/地區"打开列表
        2. 滑动查找"台灣"
        3. 点击"台灣"
        4. 点击 OK
        """
        ocr_results = page_info.get("ocr_results", [])
        screenshot, _ = self.page_detector.get_last_page_context()

        # 检查是否已经在国家列表页面（通过查找"台灣"判断）
        country_patterns = [self.TARGET_COUNTRY]
        for item in ocr_results:
            if self.TARGET_COUNTRY in item.get("text", ""):
                # 找到台湾，点击它
                logger.info(f"  -> 找到 {self.TARGET_COUNTRY}，点击选择")
                return tap_text(self.adb, ocr_results, country_patterns, wait=0.5)

        # 如果还没选择国家，点击"國家/地區"按钮打开列表
        if not self._country_selected:
            # 点击屏幕中央偏下位置（国家/地区选择按钮）
            x, y = center_point(self.adb)
            y = self.adb.scaled_y(BASE_COUNTRY_SELECT_Y)
            logger.info("  -> 点击打开国家/地区列表")
            self.adb.tap(x, y)
            return ActionResult.ok(wait=1.0)

        # 已经选择了国家，点击 OK 确认
        ok_patterns = _get_patterns("popup_ok")
        result = tap_text(self.adb, ocr_results, ok_patterns, wait=1.0)
        if result:
            self._country_selected = True
            logger.info("  -> 点击 OK 确认国家选择")
            return result

        return ActionResult.ok(wait=1.0)

    def _handle_terms_privacy(self, page_info: dict) -> ActionResult:
        """
        处理条款与隐私页面

        流程：
        1. 点击"使用條款"，然后关闭弹窗
        2. 点击"隱私權政策"，然后关闭弹窗
        3. 点击所有 icon_gray_yes 模板直到消失
        4. 点击 OK
        """
        ocr_results = page_info.get("ocr_results", [])
        screenshot, _ = self.page_detector.get_last_page_context()

        # 步骤1: 点击使用条款（如果还没点击）
        if not self._terms_clicked:
            terms_patterns = _get_patterns("init_terms_btn")
            result = tap_text(self.adb, ocr_results, terms_patterns, wait=1.0)
            if result:
                self._terms_clicked = True
                logger.info("  -> 点击使用条款")
                return result

        # 步骤2: 点击隐私政策（如果还没点击）
        if not self._privacy_clicked:
            privacy_patterns = _get_patterns("init_privacy_btn")
            result = tap_text(self.adb, ocr_results, privacy_patterns, wait=1.0)
            if result:
                self._privacy_clicked = True
                logger.info("  -> 点击隐私政策")
                return result

        # 步骤3: 点击灰色勾选图标
        if not self._gray_yes_clicked:
            match = self.page_detector.find_template_with_scale(
                "icon_gray_yes", screenshot=screenshot
            )
            if match:
                logger.info("  -> 点击灰色勾选图标")
                return tap_box(self.adb, match.box, wait=0.5)
            else:
                self._gray_yes_clicked = True

        # 步骤4: 点击 OK
        ok_patterns = _get_patterns("popup_ok")
        result = tap_text(self.adb, ocr_results, ok_patterns, wait=1.0)
        if result:
            self._terms_accepted = True
            logger.info("  -> 条款同意完成")
            return result

        return ActionResult.ok(wait=1.0)

    def _handle_create_save(self, page_info: dict) -> ActionResult:
        """
        处理创建存档页面

        点击"從頭開始"按钮
        """
        ocr_results = page_info.get("ocr_results", [])

        # 点击"從頭開始"
        start_patterns = _get_patterns("init_start_from_scratch")
        result = tap_text(self.adb, ocr_results, start_patterns, wait=1.0)
        if result:
            logger.info("  -> 点击从头开始")
            return result

        # 如果没有找到文字，尝试点击 OK
        ok_patterns = _get_patterns("popup_ok")
        result = tap_text(self.adb, ocr_results, ok_patterns, wait=1.0)
        if result:
            self._save_created = True
            return result

        return ActionResult.ok(wait=1.0)

    def _handle_account_link(self, page_info: dict) -> ActionResult:
        """
        处理账号链接页面

        点击"現在不連結"跳过账号链接
        """
        ocr_results = page_info.get("ocr_results", [])

        skip_patterns = _get_patterns("init_skip_link")
        result = tap_text(self.adb, ocr_results, skip_patterns, wait=1.0)
        if result:
            logger.info("  -> 点击跳过账号链接")
            return result

        return ActionResult.ok(wait=1.0)

    def _handle_set_nickname(self, page_info: dict) -> ActionResult:
        """
        处理设置昵称页面

        流程：
        1. 点击铅笔图标
        2. 进入昵称输入页面
        """
        screenshot, _ = self.page_detector.get_last_page_context()

        # 点击铅笔图标
        match = self.page_detector.find_template_with_scale(
            "icon_pencil", screenshot=screenshot
        )
        if match:
            logger.info("  -> 点击铅笔图标编辑昵称")
            return tap_box(self.adb, match.box, wait=1.0)

        # 如果已经设置了昵称，点击 OK
        if self._nickname_set:
            ok_patterns = _get_patterns("popup_ok")
            result = tap_text(self.adb, page_info.get("ocr_results", []), ok_patterns, wait=1.0)
            if result:
                return result

        return ActionResult.ok(wait=1.0)

    def _handle_nickname_input(self, page_info: dict) -> ActionResult:
        """
        处理昵称输入页面

        流程：
        1. 点击屏幕中心（输入框位置）
        2. 输入昵称
        3. 点击 OK
        """
        ocr_results = page_info.get("ocr_results", [])

        # 点击输入框位置（屏幕中央）
        x, y = center_point(self.adb)
        y = self.adb.scaled_y(BASE_NICKNAME_INPUT_Y)
        logger.info(f"  -> 点击输入框，输入昵称: {self.TARGET_NICKNAME}")
        self.adb.tap(x, y)
        time.sleep(0.5)

        # 输入昵称
        self.adb.input_text(self.TARGET_NICKNAME)
        time.sleep(0.5)

        # 点击 OK
        ok_patterns = _get_patterns("popup_ok")
        result = tap_text(self.adb, ocr_results, ok_patterns, wait=1.0)
        if result:
            self._nickname_set = True
            logger.info("  -> 昵称设置完成")
            return result

        return ActionResult.ok(wait=1.0)

    def _handle_confirm_settings(self, page_info: dict) -> ActionResult:
        """
        处理确认设置页面

        点击 OK 确认设置
        """
        ocr_results = page_info.get("ocr_results", [])

        ok_patterns = _get_patterns("popup_ok")
        result = tap_text(self.adb, ocr_results, ok_patterns, wait=1.0)
        if result:
            logger.info("  -> 确认设置")
            return result

        return ActionResult.ok(wait=1.0)

    def _handle_select_pack(self, page_info: dict) -> ActionResult:
        """
        处理选择初始卡包页面

        选择第一个卡包（点击屏幕中央偏下位置）
        """
        logger.info("  -> 选择初始卡包")
        x = self.adb.scaled_x(BASE_PACK_SELECT_X)
        y = self.adb.scaled_y(BASE_PACK_SELECT_Y)
        self.adb.tap(x, y)
        self._pack_selected = True
        return ActionResult.ok(wait=1.0)

    def _handle_swipe_open(self, page_info: dict) -> ActionResult:
        """
        处理滑动开包引导页面

        横向滑动来开封
        """
        logger.info("  -> 滑动开包")
        start_x = self.adb.scaled_x(BASE_SWIPE_START_X)
        end_x = self.adb.scaled_x(BASE_SWIPE_END_X)
        y = self.adb.scaled_y(BASE_SWIPE_Y)
        start = (start_x, y)
        end = (end_x, y)
        return swipe(self.adb, start, end, duration=500)

    def _handle_next_step(self, page_info: dict) -> ActionResult:
        """
        处理下一步按钮页面

        点击"下一步"
        """
        ocr_results = page_info.get("ocr_results", [])

        next_patterns = _get_patterns("init_next_step")
        result = tap_text(self.adb, ocr_results, next_patterns, wait=1.0)
        if result:
            logger.info("  -> 点击下一步")
            return result

        # 如果没有找到"下一步"，尝试点击 OK
        ok_patterns = _get_patterns("popup_ok")
        result = tap_text(self.adb, ocr_results, ok_patterns, wait=1.0)
        if result:
            return result

        # 默认点击屏幕中央
        return tap_center(self.adb, wait=1.0)

    def _handle_mission(self, page_info: dict) -> ActionResult:
        """
        处理任务引导页面

        点击"任務"按钮
        """
        ocr_results = page_info.get("ocr_results", [])

        mission_patterns = _get_patterns("init_mission")
        result = tap_text(self.adb, ocr_results, mission_patterns, wait=1.0)
        if result:
            logger.info("  -> 点击任务")
            return result

        return ActionResult.ok(wait=1.0)

    def _handle_enjoy(self, page_info: dict) -> ActionResult:
        """
        处理完成页面

        点击屏幕任意位置继续，标记任务完成
        """
        logger.info("  -> 初始化完成，点击继续")
        self._phase = InitAccountPhase.COMPLETED
        self._pack_opened = True
        return tap_center(self.adb, wait=2.0)

    def _handle_pack_opening_result(self, page_info: dict) -> ActionResult:
        """
        处理开包结果页面

        点击继续按钮
        """
        ocr_results = page_info.get("ocr_results", [])

        # 点击"繼續"或"點擊來繼續"
        continue_patterns = _get_patterns("continue_button")
        result = tap_text(self.adb, ocr_results, continue_patterns, wait=1.0)
        if result:
            logger.info("  -> 点击继续")
            return result

        # 如果没有找到，点击屏幕中央
        return tap_center(self.adb, wait=1.0)

    def _handle_card_register(self, page_info: dict) -> ActionResult:
        """
        处理卡牌登录页面

        向上滑动卡牌
        """
        logger.info("  -> 向上滑动登录卡牌")
        start, end = self._swipe_card_coords()
        return swipe(self.adb, start, end, duration=100)

    def _handle_opening_card(self, page_info: dict) -> ActionResult:
        """
        处理卡牌展示页面

        长按跳过
        """
        ocr_results = page_info.get("ocr_results", [])
        long_press_patterns = _get_patterns("long_press")

        # 查找"長按"文字位置并长按
        for item in ocr_results:
            text = item.get("text", "")
            for pattern in long_press_patterns:
                if pattern in text:
                    box = item.get("box", {})
                    if box:
                        x = (box["x1"] + box["x2"]) // 2
                        y = (box["y1"] + box["y2"]) // 2
                        logger.info("  -> 长按跳过卡牌展示")
                        self.adb.long_press(x, y, duration=1000)
                        return ActionResult.ok(wait=2.0)

        return ActionResult.ok(wait=2.0)

    def _swipe_card_coords(self) -> tuple[tuple[int, int], tuple[int, int]]:
        """
        获取卡牌登录滑动的坐标

        Returns:
            (start, end) 坐标元组
        """
        # 屏幕中央偏下位置向上滑动
        x = self.adb.scaled_x(540)
        start_y = self.adb.scaled_y(1400)
        end_y = self.adb.scaled_y(600)
        return ((x, start_y), (x, end_y))
