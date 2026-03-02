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

from ptcgp_auto_v2.config.settings import get_settings
from ptcgp_auto_v2.core.task_base import (
    ActionResult,
    ResetType,
    Task,
    TaskRegistry,
    TaskResult,
)
from ptcgp_auto_v2.db.repositories import (
    AccountBattleProgressRepository,
    BattleTaskConfigRepository,
    CardRepository,
)
from ptcgp_auto_v2.locales import get_text_patterns
from ptcgp_auto_v2.utils.pack_image_manager import PackImageManager

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)


# ============================================================
# 停止条件类
# ============================================================

class StopCondition:
    """停止条件基类"""

    def __init__(self, config: dict):
        self.config = config

    def check(self, task: "BattleTask") -> bool:
        """检查是否满足停止条件，子类实现"""
        return False


class TimeLimitCondition(StopCondition):
    """A: 时间限制停止条件

    配置示例: {"type": "time", "value": 30}
    """

    def check(self, task: "BattleTask") -> bool:
        if not task._start_time:
            return False
        minutes = self.config.get("value", 0)
        elapsed = datetime.now() - task._start_time
        return elapsed >= timedelta(minutes=minutes)


class BattleCountCondition(StopCondition):
    """B: 对战次数停止条件

    配置示例: {"type": "count", "value": 10}
    """

    def check(self, task: "BattleTask") -> bool:
        count = self.config.get("value", 0)
        return task._battle_count >= count


class HourglassCondition(StopCondition):
    """C: 沙漏获取停止条件

    配置示例: {"type": "hourglass", "value": 3}
    """

    def check(self, task: "BattleTask") -> bool:
        # TODO: 实现沙漏数量检查
        return False


class LevelCompleteCondition(StopCondition):
    """D: 等级完成停止条件

    配置示例: {"type": "level_complete", "set_code": "A1", "level": "精英"}
    """

    def check(self, task: "BattleTask") -> bool:
        set_code = self.config.get("set_code")
        level = self.config.get("level")
        if not set_code or not level:
            return False
        return task._progress_repo.is_level_completed(
            task._account_id, set_code, level
        )


class NoRewardCondition(StopCondition):
    """E: 无首次过关奖励停止条件

    配置示例: {"type": "no_reward"}
    """

    def check(self, task: "BattleTask") -> bool:
        # TODO: 实现无奖励检测
        return False


# 停止条件工厂
STOP_CONDITION_FACTORIES = {
    "time": TimeLimitCondition,
    "count": BattleCountCondition,
    "hourglass": HourglassCondition,
    "level_complete": LevelCompleteCondition,
    "no_reward": NoRewardCondition,
}


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
        # 数据仓库
        self._progress_repo = AccountBattleProgressRepository()
        self._config_repo = BattleTaskConfigRepository()
        self._card_repo = CardRepository()
        # PackImageManager 用于系列选择
        self._pack_manager = PackImageManager()
        # 运行时状态
        self._account_id: int = 0
        self._task_instance_id: int = 0
        self._stop_conditions: list[StopCondition] = []
        self._start_time: Optional[datetime] = None
        self._battle_count: int = 0
        self._hourglass_before: int = 0
        self._hourglass_gained: int = 0
        # 系列选择缓存：该系列的所有子包模板名
        self._series_pack_names: list[str] = []
        # 标记是否已预加载模板
        self._templates_preloaded: bool = False

    def _get_target_set_code(self, stop_conditions: list[dict]) -> str:
        """从停止条件中获取目标系列代码"""
        for condition in stop_conditions:
            if condition.get("type") == "level_complete":
                return condition.get("set_code", "")
        return ""

    def _get_target_level(self, stop_conditions: list[dict]) -> str:
        """从停止条件中获取目标等级"""
        for condition in stop_conditions:
            if condition.get("type") == "level_complete":
                return condition.get("level", "")
        return ""

    def on_start(self):
        """加载停止条件和目标配置"""
        logger.info("[BattleTask] 任务开始")

        # 从 task_instance 获取账号和任务实例ID
        task_instance = getattr(self, 'task_instance', None)
        if task_instance:
            self._account_id = getattr(task_instance, 'account_id', 0)
            self._task_instance_id = getattr(task_instance, 'id', 0)

        # 从 BattleTaskConfig 获取停止条件
        stop_conditions_config = self._config_repo.get_stop_conditions(self._task_instance_id)
        self._stop_conditions = self._parse_stop_conditions(stop_conditions_config)

        target_set_code = self._get_target_set_code(stop_conditions_config)
        target_level = self._get_target_level(stop_conditions_config)

        logger.info(
            f"[BattleTask] 目标: {target_set_code} {target_level}, "
            f"停止条件: {len(self._stop_conditions)}个"
        )

        self._start_time = datetime.now()

        # 预加载目标系列的子包模板（如果有目标系列）
        if target_set_code:
            self._preload_series_templates(target_set_code)

    def _preload_series_templates(self, target_set_code: str) -> None:
        """预加载目标系列的所有子包模板"""
        if not target_set_code or self._templates_preloaded:
            return

        try:
            # 获取该系列下的所有子包
            packs = self._card_repo.get_packs_by_set_code(target_set_code)
            if not packs:
                logger.warning(f"[BattleTask] 未找到系列 {target_set_code} 的子包")
                return

            # 过滤 PROMO 子包，缓存模板名
            self._series_pack_names = [
                p.name for p in packs
                if not (p.set_code or "").upper().startswith("PROMO")
            ]

            # 预加载所有模板
            _, template_matcher = self.recognizer
            for pack_name in self._series_pack_names:
                self._pack_manager.ensure_template_ready(template_matcher, pack_name)

            self._templates_preloaded = True
            logger.info(
                f"[BattleTask] 预加载系列 {target_set_code} 的 {len(self._series_pack_names)} 个子包模板"
            )

        except Exception as e:
            logger.error(f"[BattleTask] 预加载系列模板失败: {e}")

    def _find_series_in_screenshot(self, screenshot, target_set_code: str) -> Optional[tuple[int, int, int, int]]:
        """
        在当前截图中查找目标系列位置

        Args:
            screenshot: 截图
            target_set_code: 目标系列代码

        Returns:
            匹配到的模板位置 (x1, y1, x2, y2)，未找到返回 None
        """
        if not self._series_pack_names:
            return None

        _, template_matcher = self.recognizer
        settings = get_settings()

        for pack_name in self._series_pack_names:
            template_name = self._pack_manager.get_template_name(pack_name)
            match = template_matcher.find_with_scale(
                screenshot,
                template_name,
                scale=settings.scale_battle_series_select,
                threshold=settings.pack_template_threshold,
            )
            if match:
                logger.info(f"[BattleTask] 找到系列 {target_set_code}，通过子包 {pack_name}")
                return match.box

        return None

    def _parse_stop_conditions(self, configs: list[dict]) -> list[StopCondition]:
        """解析停止条件配置"""
        conditions = []
        for config in configs:
            condition_type = config.get('type')
            factory = STOP_CONDITION_FACTORIES.get(condition_type)
            if factory:
                conditions.append(factory(config))
            else:
                logger.warning(f"[BattleTask] 未知的停止条件类型: {condition_type}")
        return conditions

    def is_completed(self) -> bool:
        """检查是否满足任一停止条件"""
        if not self._stop_conditions:
            return False

        for condition in self._stop_conditions:
            if condition.check(self):
                logger.info(f"[BattleTask] 停止条件满足: {condition.config}")
                return True

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
