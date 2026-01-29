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
# 常量定义
# ============================================================

# 昵称输入框 Y 坐标（基准 1080x1920）
INPUT_BOX_Y = 860

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


from ptcgp_auto_v2.utils.gesture import (
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
)


def _get_patterns(key: str) -> list[str]:
    """获取指定配置的文本列表"""
    return get_text_patterns(key)


def _is_text_visible(ocr_results: list[dict], text: str) -> bool:
    """检查 OCR 结果中是否包含指定文字"""
    for item in ocr_results:
        if text in item.get("text", ""):
            return True
    return False


# ============================================================
# 页面识别规则
# 注意：priority 数值越小优先级越高
# ============================================================
def _build_init_pages() -> list[dict]:
    """构建新账号初始化任务页面规则"""
    return [
        {"name": "init_select_country", "identifiers": _get_patterns("init_select_country"), "priority": 99},
        {"name": "init_terms_privacy", "identifiers": _get_patterns("init_terms_privacy"), "priority": 99},
        {"name": "init_data_use", "identifiers": _get_patterns("init_data_use"), "priority": 98},
        {"name": "init_create_save", "identifiers": _get_patterns("init_create_save"), "priority": 99},
        {"name": "init_account_link", "identifiers": _get_patterns("init_account_link"), "priority": 99},
        {"name": "init_set_nickname", "identifiers": _get_patterns("init_set_nickname"), "priority": 99},
        {"name": "init_nickname_input", "identifiers": _get_patterns("init_nickname_title"), "exact_match": True, "priority": 99},
        {"name": "init_confirm_settings", "identifiers": _get_patterns("init_confirm_settings"), "priority": 99},
        {"name": "init_select_pack", "identifiers": _get_patterns("init_select_pack"), "priority": 99},
        {"name": "init_decide", "identifiers": _get_patterns("init_decide"), "exact_match": True, "priority": 99},
        {"name": "init_swipe_open", "identifiers": _get_patterns("init_swipe_open"), "priority": 99},
        {"name": "init_next_step", "identifiers": _get_patterns("init_next_step"), "exact_match": True, "priority": 99},
        {"name": "init_open_pack", "identifiers": _get_patterns("init_open_pack"), "exact_match": True, "priority": 99},
        {"name": "init_enjoy", "identifiers": _get_patterns("init_enjoy"), "priority": 99},
        {"name": "init_tap_to_flip", "identifiers": _get_patterns("init_tap_to_flip"), "priority": 99},
        {"name": "init_select_favorite_card", "identifiers": _get_patterns("init_select_favorite_card"), "priority": 99},
        {"name": "pack_opening_result", "identifiers": _get_patterns("pack_opening_result"), "priority": 99},
        {"name": "pack_card_register", "identifiers": _get_patterns("pack_card_register"), "priority": 99},
        {"name": "pack_opening_card", "identifiers": _get_patterns("long_press"), "priority": 99},
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
    reset_type = ResetType.ONCE  # 一次性任务
    max_iterations = 300
    max_unknown_pages = 30
    pages = _build_init_pages()

    # 目标国家/地区
    TARGET_COUNTRY = "香港"
    # 目标昵称
    TARGET_NICKNAME = "skn"
    # 出生年份偏移（当前年份 - OFFSET）
    BIRTH_YEAR_OFFSET = 20
    # 出生月份
    BIRTH_MONTH = 2

    def __init__(self, adb, recognizer, page_detector):
        super().__init__(adb, recognizer, page_detector)

        # 核心状态机（用于页面间流转）
        self._phase = InitAccountPhase.INIT

        # 页面内操作缓存（key格式: 页面名_操作名）
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

        # 快进按钮
        if page_name == "speed_up_button":
            return tap_matched_element(self.adb, page_info) or ActionResult.ok()

        # 选择国家/地区页面
        if page_name == "init_select_country":
            return self._handle_select_country(page_info)

        # 条款与隐私页面
        if page_name == "init_terms_privacy":
            return self._handle_terms_privacy(page_info)

        if page_name == "init_data_use":
            return self._handle_data_use(page_info)

        # 创建存档页面
        if page_name == "init_create_save":
            return self._handle_create_save(page_info)

        # 账号链接页面
        if page_name == "init_account_link":
            return self._handle_account_link(page_info)

        # 设置昵称页面（包含昵称输入）
        if page_name in ("init_set_nickname", "init_nickname_input"):
            return self._handle_set_nickname(page_info)

        # 确认设置页面
        if page_name == "init_confirm_settings":
            return self._handle_confirm_settings(page_info)

        # 选择卡包页面
        if page_name == "init_select_pack":
            return self._handle_select_pack(page_info)

        # 决定按钮页面
        if page_name == "init_decide":
            return self._handle_decide(page_info)

        # 滑动开包引导页面
        if page_name == "init_swipe_open":
            return self._handle_swipe_open(page_info)

        # 下一步按钮页面
        if page_name == "init_next_step":
            return self._handle_next_step(page_info)

        # 开封按钮页面
        if page_name == "init_open_pack":
            return self._handle_open_pack(page_info)

        # 翻开卡牌页面
        if page_name == "init_tap_to_flip":
            return self._handle_tap_to_flip(page_info)

        # 选择喜欢的卡牌页面
        if page_name == "init_select_favorite_card":
            return self._handle_select_favorite_card(page_info)

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

        # 其他页面
        logger.warning(f"未处理的页面: {page_name}")
        return ActionResult.ok(wait=1.0)

    def handle_unknown_page(self, page_info) -> ActionResult:
        """
        处理未知页面

        点击屏幕中心兜底，然后等待重新识别
        """
        logger.debug("未知页面，点击屏幕中心兜底")
        # 适配最后进入主页的任务点击（点击其他地方不行）
        tap_text_exact(self.adb, page_info.get("ocr_results", []), get_text_patterns("text_task"))
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

    def _tap_text_or_wait(self, ocr_results: list, pattern_key: str, exact: bool = False, wait: float = 1.0) -> ActionResult:
        """尝试点击文本，失败则返回 wait 结果"""
        result = tap_text(self.adb, ocr_results, _get_patterns(pattern_key), exact=exact, wait=wait)
        return result if result else ActionResult.ok(wait=wait)

    def _handle_select_country(self, page_info: dict) -> ActionResult:
        """
        处理选择国家/地区页面

        流程：
        1. 点击「國家/地區」打开列表
        2. 从上往下滑动查找 TARGET_COUNTRY（台湾）
        3. 点击 TARGET_COUNTRY
        4. 点击「年」，上滑选择年份
        5. 点击「月」，点击 2
        6. 点击 OK
        """
        ocr_results = page_info.get("ocr_results", [])

        # 操作 1: 如果页面上已经出现目标国家，说明已经选好了，直接进行下一步
        if not self._is_action_done("select_country_list_opened"):
            if _is_text_visible(ocr_results, self.TARGET_COUNTRY):
                logger.info(f"  -> 检测到目标国家 {self.TARGET_COUNTRY} 已选择，跳过国家选择")
                self._mark_action_done("select_country_country_clicked")
                self._mark_action_done("select_country_list_opened")
            else:
                # 点击「國家/地區」打开列表
                country_btn_patterns = _get_patterns("init_country_btn")
                result = tap_text_exact(self.adb, ocr_results, country_btn_patterns, wait=1.0)
                if result:
                    logger.info("  -> 点击「國家/地區」打开列表")
                    self._mark_action_done("select_country_list_opened")
                    return result
                return ActionResult.ok()

        # 操作 2: 在国家列表中查找并点击 TARGET_COUNTRY
        if not self._is_action_done("select_country_country_clicked"):
            if _is_text_visible(ocr_results, self.TARGET_COUNTRY):
                logger.info(f"  -> 找到 {self.TARGET_COUNTRY}，点击选择")
                result = tap_text_exact(self.adb, ocr_results, [self.TARGET_COUNTRY], wait=0.5)
                if result:
                    self._mark_action_done("select_country_country_clicked")
                    return result
            else:
                # 从上往下滑动查找（国家列表是字母顺序，台湾在较下方）
                logger.info("  -> 滑动查找目标国家")
                return swipe_up(self.adb, ratio=0.3, wait=1.0)

        # 操作 3: 点击「年」打开年份选择列表
        if not self._is_action_done("select_country_year_clicked"):
            year_btn_patterns = _get_patterns("init_year_btn")
            if _is_text_visible(ocr_results, year_btn_patterns[0]):
                result = tap_text_exact(self.adb, ocr_results, year_btn_patterns, wait=1.0)
                if result:
                    logger.info("  -> 点击「年」打开年份选择")
                    self._mark_action_done("select_country_year_clicked")
                    return result

        # 操作 4: 在年份列表中查找并选择目标年份
        if self._is_action_done("select_country_year_clicked") and not self._is_action_done("select_country_year_selected"):
            target_year = str(datetime.now().year - self.BIRTH_YEAR_OFFSET)
            if _is_text_visible(ocr_results, target_year):
                logger.info(f"  -> 找到年份 {target_year}，点击选择")
                result = tap_text_exact(self.adb, ocr_results, [target_year], wait=0.5)
                if result:
                    self._mark_action_done("select_country_year_selected")
                    return result
            else:
                # 上滑查找年份（较新年份在上方）
                # 年份选择列表在屏幕左下角，从左下角中心开始上滑
                logger.info("  -> 上滑查找目标年份")
                start_x = self.adb.scaled_x(300)  # 左下角区域 x
                start_y = self.adb.scaled_y(1400)  # 左下角区域 y
                end_y = self.adb.scaled_y(900)  # 上滑目标 y
                return swipe(self.adb, (start_x, end_y), (start_x, start_y), duration=300, wait=1.0)

        # 操作 5: 点击「月」打开月份选择列表
        if not self._is_action_done("select_country_month_clicked"):
            month_btn_patterns = _get_patterns("init_month_btn")
            if _is_text_visible(ocr_results, month_btn_patterns[0]):
                result = tap_text_exact(self.adb, ocr_results, month_btn_patterns, wait=1.0)
                if result:
                    logger.info("  -> 点击「月」打开月份选择")
                    self._mark_action_done("select_country_month_clicked")
                    return result

        # 操作 6: 在月份列表中点击「2」
        if self._is_action_done("select_country_month_clicked") and not self._is_action_done("select_country_month_selected"):
            month_2_patterns = _get_patterns("init_month_2")
            result = tap_text_exact(self.adb, ocr_results, month_2_patterns, wait=0.5)
            if result:
                logger.info("  -> 选择月份 2")
                self._mark_action_done("select_country_month_selected")
                return result

        # 最后点击 OK 完成整个页面
        result = tap_text_exact(self.adb, ocr_results, get_text_patterns("popup_ok"))
        return ActionResult.ok(wait=1.0)

    def _handle_data_use(self, page_info: dict) -> ActionResult:
        logger.debug(f"matched_text: {page_info.get('matched_text')}")
        matches = self.page_detector.find_all_templates("icon_gray_yes", threshold=0.95, scale=0.72)
        if matches:
            for match in matches:
                if match.box[0]< self.adb.center_x():
                  logger.debug(f"  -> 跳过勾选图标位置: {match.box[0]} x {match.box[1]}")
                  continue
                logger.debug(f"  -> 点击勾选图标位置: {match.box[0]} x {match.box[1]}")
                tap_box(self.adb, match.box, wait=0)

        ocr_results = page_info.get("ocr_results", [])
        ok_result = tap_text_exact(self.adb, ocr_results, _get_patterns("popup_ok"), wait=1.0)
        if ok_result:
            return ok_result
        return ActionResult.ok()

    def _handle_terms_privacy(self, page_info: dict) -> ActionResult:
        """
        处理条款与隐私页面

        流程：
        1. 点击「使用條款」（common 会自动处理关闭弹窗）
        2. 点击「隱私權政策」（common 会自动处理关闭弹窗）
        3. 点击所有 icon_gray_yes 模板直到消失
        4. 点击 OK（common 会自动处理）
        """
        ocr_results = page_info.get("ocr_results", [])
        screenshot, _ = self.page_detector.get_last_page_context()

        # 看到x就点掉
        click_close(self.adb, self.page_detector, ocr_results, get_text_patterns("text_x"))
        tap_template(self.adb, self.page_detector, template_name="btn_back", threshold=0.95)

        # 操作 1: 点击「使用條款」（关闭弹窗由 common 处理）
        if not self._is_action_done("terms_privacy_terms_clicked"):
            terms_patterns = _get_patterns("init_terms_btn")
            result = tap_text_exact(self.adb, ocr_results, terms_patterns, wait=3)
            if result:
                logger.info("  -> 点击「使用條款」")
                self._mark_action_done("terms_privacy_terms_clicked")
                return result

        # 操作 2: 点击「隱私權政策」（关闭弹窗由 common 处理）
        if not self._is_action_done("terms_privacy_privacy_clicked"):
            privacy_patterns = _get_patterns("init_privacy_btn")
            result = tap_text_exact(self.adb, ocr_results, privacy_patterns, wait=3)
            if result:
                logger.info("  -> 点击「隱私權政策」")
                self._mark_action_done("terms_privacy_privacy_clicked")
                return result

        # 操作 3: 点击所有灰色勾选图标直到消失
        match = self.page_detector.find_template("icon_gray_yes", threshold=0.95)
        if match:
            logger.info("  -> 点击灰色勾选图标")
            return tap_box(self.adb, match, wait=0.1)

        # 操作 4: 点击 OK 完成页面
        ok_patterns = _get_patterns("popup_ok")
        result = tap_text_exact(self.adb, ocr_results, ok_patterns, wait=0.5)

        return ActionResult.ok(wait=1.0)

    def _handle_create_save(self, page_info: dict) -> ActionResult:
        """
        处理创建存档页面

        点击「從頭開始」按钮
        """
        ocr_results = page_info.get("ocr_results", [])
        result = tap_text(self.adb, ocr_results, _get_patterns("init_start_from_scratch"), exact=True, wait=1.0)
        if result:
            logger.info("  -> 点击「從頭開始」")
        return result or ActionResult.ok(wait=1.0)

    def _handle_account_link(self, page_info: dict) -> ActionResult:
        """
        处理账号链接页面

        点击「現在不連結」跳过账号链接
        """
        ocr_results = page_info.get("ocr_results", [])
        result = tap_text(self.adb, ocr_results, _get_patterns("init_skip_link"), exact=True, wait=1.0)
        if result:
            logger.info("  -> 点击「現在不連結」跳过账号链接")
        return result or ActionResult.ok(wait=1.0)

    def _handle_set_nickname(self, page_info: dict) -> ActionResult:
        """
        处理设置昵称页面（包含昵称输入流程）

        流程：
        1. 点击铅笔图标进入输入页面
        2. 点击输入框
        3. 输入昵称
        4. 点击 OK
        5. 检测到昵称出现则完成
        """
        ocr_results = page_info.get("ocr_results", [])
        screenshot, _ = self.page_detector.get_last_page_context()

        # 检查昵称是否已设置成功（页面上能看到 skn）
        if _is_text_visible(ocr_results, self.TARGET_NICKNAME):
            logger.info(f"  -> 检测到昵称 {self.TARGET_NICKNAME} 已设置，点击 OK 完成")
            ok_patterns = _get_patterns("popup_ok")
            result = tap_text(self.adb, ocr_results, ok_patterns, wait=1.0)
            if result:
                return result
            return ActionResult.ok(wait=1.0)

        # 操作 1: 点击铅笔图标
        match = self.page_detector.find_template_with_scale("icon_pencil", screenshot=screenshot)
        if match:
            logger.info("  -> 点击铅笔图标编辑昵称")
            return tap_box(self.adb, match.box, wait=1.0)

        # 操作 2: 点击输入框并输入昵称
        result = tap(self.adb, self.adb.center_x(), INPUT_BOX_Y, wait=0.5)
        if result:
            logger.info(f"  -> 点击输入框，输入昵称: {self.TARGET_NICKNAME}")
            self.adb.device.send_keys(self.TARGET_NICKNAME)
            time.sleep(0.5)

        # 操作 3: 点击 OK
        ok_patterns = _get_patterns("popup_ok")
        result = tap_text(self.adb, ocr_results, ok_patterns, wait=1.0)
        if result:
            return result

        return ActionResult.ok(wait=1.0)

    def _handle_confirm_settings(self, page_info: dict) -> ActionResult:
        """
        处理确认设置页面

        点击 OK 确认设置
        """
        ocr_results = page_info.get("ocr_results", [])
        result = tap_text(self.adb, ocr_results, _get_patterns("popup_ok"), wait=1.0)
        if result:
            logger.info("  -> 确认设置")
        return result or ActionResult.ok(wait=1.0)

    def _handle_select_pack(self, page_info: dict) -> ActionResult:
        """
        处理选择初始卡包页面

        点击屏幕中央选择卡包
        """
        logger.info("  -> 选择初始卡包")
        return tap_center(self.adb, wait=1.0)

    def _handle_decide(self, page_info: dict) -> ActionResult:
        """
        处理决定页面

        点击「決定」按钮
        """
        ocr_results = page_info.get("ocr_results", [])
        result = tap_text(self.adb, ocr_results, _get_patterns("init_decide"), exact=True, wait=1.0)
        if result:
            logger.info("  -> 点击「決定」")
        return result or ActionResult.ok(wait=1.0)

    def _handle_swipe_open(self, page_info: dict) -> ActionResult:
        """
        处理滑动开包引导页面

        直接调用 OpenPackTask 的方法
        """
        logger.info("  -> 滑动开包")
        open_pack_task = _get_open_pack_task(self.adb, self.recognizer, self.page_detector)
        return open_pack_task._handle_opening_swipe(page_info)

    def _handle_next_step(self, page_info: dict) -> ActionResult:
        """
        处理下一步按钮页面

        点击「下一步」
        """
        ocr_results = page_info.get("ocr_results", [])
        result = tap_text(self.adb, ocr_results, _get_patterns("init_next_step"), exact=True, wait=1.0)
        if result:
            logger.info("  -> 点击「下一步」")
        return result or ActionResult.ok(wait=1.0)

    def _handle_mission(self, page_info: dict) -> ActionResult:
        """
        处理任务引导页面

        点击「任務」按钮
        """
        ocr_results = page_info.get("ocr_results", [])
        result = tap_text(self.adb, ocr_results, _get_patterns("init_mission"), exact=True, wait=1.0)
        if result:
            logger.info("  -> 点击「任務」")
        return result or ActionResult.ok(wait=1.0)

    def _handle_open_pack(self, page_info: dict) -> ActionResult:
        """
        处理开封按钮页面

        点击「開封」按钮
        """
        ocr_results = page_info.get("ocr_results", [])
        result = tap_text(self.adb, ocr_results, _get_patterns("init_open_pack"), exact=True, wait=1.0)
        if result:
            logger.info("  -> 点击「開封」")
        return result or ActionResult.ok(wait=1.0)

    def _handle_tap_to_flip(self, page_info: dict) -> ActionResult:
        """
        处理翻开卡牌页面

        快速点击屏幕中心翻开卡牌
        """
        logger.info("  -> 快速点击翻开卡牌")
        return quick_tap(self.adb, wait=0.5)

    def _handle_select_favorite_card(self, page_info: dict) -> ActionResult:
        """
        处理选择喜欢的卡牌页面

        点击 center_x, scale_y(740) 位置
        """
        logger.info("  -> 选择喜欢的卡牌")
        tap_x = self.adb.center_x()
        tap_y = self.adb.scaled_y(740)
        return tap(self.adb, tap_x, tap_y, wait=1.0)

    def _handle_enjoy(self, page_info: dict) -> ActionResult:
        """
        处理完成页面

        点击屏幕任意位置继续，标记任务完成
        """
        logger.info("  -> 初始化完成，点击继续")
        self._phase = InitAccountPhase.COMPLETED
        return tap_center(self.adb, wait=2.0)

    def _handle_pack_opening_result(self, page_info: dict) -> ActionResult:
        """
        处理开包结果页面

        直接调用 OpenPackTask 的方法
        """
        open_pack_task = _get_open_pack_task(self.adb, self.recognizer, self.page_detector)
        return open_pack_task._handle_pack_opening_result(page_info)

    def _handle_card_register(self, page_info: dict) -> ActionResult:
        """
        处理卡牌登录页面

        直接调用 OpenPackTask 的方法
        """
        open_pack_task = _get_open_pack_task(self.adb, self.recognizer, self.page_detector)
        return open_pack_task._handle_card_register(page_info)

    def _handle_opening_card(self, page_info: dict) -> ActionResult:
        """
        处理卡牌展示页面

        直接调用 OpenPackTask 的方法
        """
        open_pack_task = _get_open_pack_task(self.adb, self.recognizer, self.page_detector)
        return open_pack_task._handle_opening_card(page_info)
