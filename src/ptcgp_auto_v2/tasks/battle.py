# -*- coding: utf-8 -*-
"""
对战任务模块

通过停止条件驱动刷经验获取沙漏。
停止条件包含目标信息（set_code, level）。

页面规则基于 v1 PAGES_BATTLE + PAGES_TUTORIAL 改造，
去掉与 common.py 重复的页面（popup_ok、网络错误、手指图标等）。
"""

import logging
from datetime import datetime, timedelta
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
# 页面识别规则（仅 battle 特有页面，不含 common 已处理的）
# ============================================================


def _build_battle_pages() -> list[dict[str, object]]:
    """构建对战任务页面规则

    优先级设计（数字越小越优先）：
    - 1-10: 已在 common.py 中（popup_ok、网络错误、手指图标等）
    - 11-20: 对战流程中断（战败提示、继续对战确认、对战结果）
    - 21-30: 对战核心（对战中、对战准备）
    - 31-40: 卡组/系列选择（卡组列表、系列选择、难度选择）
    - 41-50: 菜单导航（对战主页、教程列表）
    - 51-60: 游戏主页/通用（game_home_main 等）
    """
    return [
        # ==================== 对战流程中断 (11-20) ====================
        # 战败提示弹窗
        # zh_Hant: "前往任務"
        {
            "name": "battle_defeat_popup",
            "identifiers": get_text_patterns("battle_defeat_popup"),
            "priority": 11,
            "exact_match": True,
        },
        # 继续对战确认
        # zh_Hant: "是" + "要繼續上次中斷的對戰嗎？"
        {
            "name": "battle_continue_confirm",
            "identifiers": get_text_patterns("battle_continue_confirm"),
            "match_all": True,
            "priority": 12,
        },
        # 经验值结算页面
        # zh_Hant: "玩家經驗值"
        {
            "name": "battle_exp_result",
            "identifiers": get_text_patterns("battle_exp_result"),
            "priority": 14,
        },
        # 对战记录页面
        # zh_Hant: "對戰紀錄"
        {
            "name": "battle_record_page",
            "identifiers": get_text_patterns("battle_record_page"),
            "priority": 15,
            "exact_match": True,
        },
        # ==================== 对战核心 (21-30) ====================
        # 对战中
        # zh_Hant: "請將基礎寶可夢放置於戰鬥場" / "你是先攻" / "你是後攻" / "對戰對手"
        {
            "name": "battle_in_progress",
            "identifiers": get_text_patterns("battle_in_progress"),
            "priority": 21,
        },
        # 对战准备页面（牌组详情）
        # zh_Hant: "對戰！" / "首次過關報酬"
        {
            "name": "battle_prepare",
            "identifiers": get_text_patterns("battle_prepare"),
            "priority": 22,
        },
        # ==================== 卡组/系列选择 (31-40) ====================
        # 卡组列表页面
        # zh_Hant: "擴充組"（排除"選擇擴充組"）
        {
            "name": "battle_deck_select",
            "identifiers": get_text_patterns("battle_deck_list"),
            "exclude_identifiers": get_text_patterns("battle_expansion_select"),
            "priority": 31,
        },
        # 系列选择页面（扩充组选择）
        # zh_Hant: "選擇擴充組"
        # 注意：v2 中通过模板匹配确定系列，OCR 仅作辅助识别
        {
            "name": "battle_series_select",
            "identifiers": get_text_patterns("battle_expansion_select"),
            "priority": 32,
        },
        # 难度选择页面（分级对战选择）
        # zh_Hant: "分級對戰"（排除"擴充組"）
        {
            "name": "battle_level_select",
            "identifiers": get_text_patterns("battle_level_select"),
            "exclude_identifiers": get_text_patterns("battle_deck_list"),
            "priority": 33,
        },
        # ==================== 教程相关 (34-40) ====================
        # 教程完成提示页面
        # zh_Hant: "若想知道更詳細的規則"
        {
            "name": "battle_tutorial_complete_hint",
            "identifiers": get_text_patterns("battle_tutorial_complete_hint"),
            "priority": 34,
        },
        # 教程列表页面
        # zh_Hant: "玩法"
        # templates: wanfa_shalou（沙漏表示未完成）
        {
            "name": "battle_tutorial_list",
            "identifiers": get_text_patterns("battle_tutorial_list"),
            "templates": ["wanfa_shalou"],
            "priority": 35,
        },
        # ==================== 菜单导航 (41-50) ====================
        # 对战主页（锁定状态）
        # zh_Hant: "與他人對戰" + template: icon_lock
        {
            "name": "battle_home_locked",
            "identifiers": get_text_patterns("battle_main_menu"),
            "templates": ["icon_lock"],
            "match_all": True,
            "priority": 41,
        },
        # 对战主页（已解锁）
        # zh_Hant: "單人對戰"（排除"與他人對戰"避免与 locked 冲突）
        {
            "name": "battle_home",
            "identifiers": get_text_patterns("battle_solo_button"),
            "exclude_identifiers": get_text_patterns("battle_main_menu"),
            "priority": 42,
        },
        # 主对战菜单（游戏主页进入后）
        # zh_Hant: "與他人對戰"
        {
            "name": "battle_main_menu",
            "identifiers": get_text_patterns("battle_main_menu"),
            "priority": 43,
        },
        # 对战模式选择页面（新版增加的中间页面）
        # zh_Hant: "分級對戰" + "隨機對戰"（同时存在以区分于难度选择页面）
        # 优先级在 battle_level_select 之前，确保先识别此页面
        {
            "name": "battle_mode_select",
            "identifiers": get_text_patterns("battle_mode_select"),
            "match_all": True,
            "priority": 32,
        },
        # ==================== 游戏主页/通用 (51-60) ====================
        # 误入开包页面
        # zh_Hant: "提供比例" + "其他擴充包"
        {
            "name": "battle_show_pack",
            "identifiers": get_text_patterns("battle_show_pack"),
            "match_all": True,
            "priority": 52,
        },
        # ==================== 兜底规则 (800+) ====================
        # 兜底：对战图标 - 当其他页面都不匹配时，如果看到对战图标就点击进入
        # 优先级较低，确保其他具体页面先被匹配
        {
            "name": "battle_icon_fallback",
            "templates": ["icon_battle"],
            "priority": 800,
        },
    ]


# ============================================================
# 对战任务类
# ============================================================


@TaskRegistry.register("battle")
class BattleTask(Task):
    """
    对战任务 - 刷经验获取沙漏

    停止条件驱动，配置示例：
    [
        {"type": "level_complete", "set_code": "A1", "level": "精英"},
        {"type": "time", "value": 30},
        {"type": "hourglass", "value": 3, "set_code": "A1", "level": "精英"},
    ]
    """

    task_type = "battle"
    reset_type = ResetType.ONCE
    pages = _build_battle_pages()

    def __init__(self, adb, recognizer, page_detector):
        super().__init__(adb, recognizer, page_detector)
        # 运行时状态
        self._stop_conditions: list[dict] = []
        self._start_time: Optional[datetime] = None
        self._battle_count: int = 0
        self._hourglass_before: int = 0

    def on_start(self):
        """加载停止条件"""
        logger.info("[BattleTask] 任务开始")
        # TODO: 从 task_instance 加载停止条件

    def is_completed(self) -> bool:
        """检查停止条件"""
        # TODO: 实现停止条件检查
        return False

    def handle_page(self, page_name: str, page_info: dict) -> ActionResult:
        """处理页面 - 分发到对应处理方法"""
        handler = getattr(self, f"_handle_{page_name}", None)
        if handler:
            return handler(page_info)
        logger.warning(f"[BattleTask] 未找到页面处理器: {page_name}")
        return ActionResult.ok(wait=1.0)

    # ==================== 对战流程中断 (11-20) ====================

    def _handle_battle_defeat_popup(self, page_info: dict) -> ActionResult:
        """处理战败提示弹窗"""
        logger.info("[BattleTask] 页面: 战败提示弹窗 -> 点击'前往任務'")
        return ActionResult.ok(wait=1.0)

    def _handle_battle_continue_confirm(self, page_info: dict) -> ActionResult:
        """处理继续对战确认弹窗"""
        logger.info("[BattleTask] 页面: 继续对战确认 -> 点击'否'（重新开始）")
        return ActionResult.ok(wait=1.0)

    def _handle_battle_exp_result(self, page_info: dict) -> ActionResult:
        """处理经验值结算页面"""
        logger.info("[BattleTask] 页面: 经验值结算 -> 点击继续")
        return ActionResult.ok(wait=1.0)

    def _handle_battle_record_page(self, page_info: dict) -> ActionResult:
        """处理对战记录页面"""
        logger.info("[BattleTask] 页面: 对战记录 -> 返回上级")
        return ActionResult.ok(wait=1.0)

    # ==================== 对战核心 (21-30) ====================

    def _handle_battle_in_progress(self, page_info: dict) -> ActionResult:
        """处理对战中页面"""
        logger.info("[BattleTask] 页面: 对战中 -> 等待对战结束")
        return ActionResult.ok(wait=5.0)

    def _handle_battle_prepare(self, page_info: dict) -> ActionResult:
        """处理对战准备页面"""
        logger.info("[BattleTask] 页面: 对战准备 -> 点击对战按钮")
        return ActionResult.ok(wait=1.0)

    # ==================== 卡组/系列选择 (31-40) ====================

    def _handle_battle_deck_select(self, page_info: dict) -> ActionResult:
        """处理卡组列表页面（选择卡包）"""
        logger.info("[BattleTask] 页面: 卡组列表 -> 寻找带沙漏的卡包")
        return ActionResult.ok(wait=1.0)

    def _handle_battle_series_select(self, page_info: dict) -> ActionResult:
        """处理系列选择页面"""
        logger.info("[BattleTask] 页面: 系列选择 -> 点击目标系列")
        return ActionResult.ok(wait=1.0)

    def _handle_battle_level_select(self, page_info: dict) -> ActionResult:
        """处理难度选择页面"""
        logger.info("[BattleTask] 页面: 难度选择 -> 点击目标难度")
        return ActionResult.ok(wait=1.0)

    # ==================== 教程相关 (34-40) ====================

    def _handle_battle_tutorial_complete_hint(self, page_info: dict) -> ActionResult:
        """处理教程完成提示页面"""
        logger.info("[BattleTask] 页面: 教程完成提示 -> 点击OK")
        return ActionResult.ok(wait=1.0)

    def _handle_battle_tutorial_list(self, page_info: dict) -> ActionResult:
        """处理教程列表页面"""
        logger.info("[BattleTask] 页面: 教程列表 -> 点击未完成教程")
        return ActionResult.ok(wait=1.0)

    # ==================== 菜单导航 (41-50) ====================

    def _handle_battle_home_locked(self, page_info: dict) -> ActionResult:
        """处理对战主页（锁定状态）"""
        logger.info("[BattleTask] 页面: 对战主页(锁定) -> 进入教程解锁")
        return ActionResult.ok(wait=1.0)

    def _handle_battle_home(self, page_info: dict) -> ActionResult:
        """处理对战主页（已解锁）"""
        logger.info("[BattleTask] 页面: 对战主页(已解锁) -> 点击单人对抗")
        return ActionResult.ok(wait=1.0)

    def _handle_battle_main_menu(self, page_info: dict) -> ActionResult:
        """处理主对战菜单"""
        logger.info("[BattleTask] 页面: 主对战菜单 -> 点击单人对战")
        return ActionResult.ok(wait=1.0)

    def _handle_battle_mode_select(self, page_info: dict) -> ActionResult:
        """处理对战模式选择页面"""
        logger.info("[BattleTask] 页面: 对战模式选择 -> 点击分级对战")
        return ActionResult.ok(wait=1.0)

    # ==================== 游戏主页/通用 (51-60) ====================

    def _handle_battle_show_pack(self, page_info: dict) -> ActionResult:
        """处理误入开包页面"""
        logger.info("[BattleTask] 页面: 误入开包页面 -> 返回对战主页")
        return ActionResult.ok(wait=1.0)

    # ==================== 兜底规则 (800+) ====================

    def _handle_battle_icon_fallback(self, page_info: dict) -> ActionResult:
        """兜底处理：检测到对战图标"""
        logger.info("[BattleTask] 页面: 兜底(对战图标)")
        return ActionResult.ok(wait=1.0)
