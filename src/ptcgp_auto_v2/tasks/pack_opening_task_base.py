# -*- coding: utf-8 -*-
"""
统一开包流程基类

将开包页面处理、识别、记录保存统一到可复用流程。
三个任务（open_pack、claim_gifts、init_account）通过覆写扩展点实现差异化。

扩展点：
- get_target_pack_context(): 获取目标卡包上下文（可选）
- get_fixed_set_code(): 获取固定的 set_code（可选，优先于 context）
- should_prepare_pack_resources(): 是否需要准备卡包图片资源
- get_pack_record_type(): 获取 pack 记录类型（必须实现）
"""

import logging
import threading
import time
from abc import abstractmethod
from collections.abc import Callable
from typing import TYPE_CHECKING

from ptcgp_auto_v2.config.settings import get_settings
from ptcgp_auto_v2.core.task_base import (
    ActionResult,
    Task,
)
from ptcgp_auto_v2.infra.card_hash_manager import get_card_hash_manager
from ptcgp_auto_v2.infra.model_manager import get_model_manager
from ptcgp_auto_v2.infra.notifier import get_notifier
from ptcgp_auto_v2.infra.yolo_card_recognizer import DetectedCard, YoloCardRecognizer
from ptcgp_auto_v2.locales import get_text_patterns
from ptcgp_auto_v2.tasks.utils.booster_inference import (
    infer_pack_by_cards,
)
from ptcgp_auto_v2.tasks.utils.high_rarity_saver import save_high_rarity_cards
from ptcgp_auto_v2.tasks.utils.pack_opening_flow import (
    long_press_opening_card,
    swipe_card_register,
    swipe_open_pack,
    tap_opening_continue,
)
from ptcgp_auto_v2.tasks.utils.pack_result_mapper import map_detected_cards
from ptcgp_auto_v2.utils.gesture import (
    quick_tap,
    tap_center,
    tap_matched_element,
)
from ptcgp_auto_v2.utils.pack_image_manager import PackImageManager
from ptcgp_auto_v2.tasks.utils.pack_template_matcher import (
    PackCandidate,
    PackTemplateMatcher,
    build_pack_template_matcher,
)

if TYPE_CHECKING:
    from ptcgp_auto_v2.db.repositories import (
        AccountCardRepository,
        AccountPackPointRepository,
        CardRepository,
        PackRecordRepository,
    )

logger = logging.getLogger(__name__)


# ============================================================
# 通用开包页面规则构建
# ============================================================


def build_pack_opening_pages() -> list[dict]:
    """构建开包流程通用页面规则

    包含开包过程中的标准页面：
    - 横向滑动开包
    - 长按开包卡牌
    - 卡牌注册
    - 开包结果
    """
    return [
        # 横向滑動來開封
        {
            "name": "pack_opening_swipe",
            "identifiers": get_text_patterns("pack_opening_swipe"),
            "priority": 99,
        },
        # 點擊想开封的擴充包
        {
            "name": "pack_opening_select",
            "identifiers": get_text_patterns("pack_opening_select"),
            "priority": 99,
        },
        # 長按開封
        {
            "name": "pack_opening_card",
            "identifiers": get_text_patterns("long_press"),
            "priority": 99,
        },
        # 開封結果 / 開包點數 / 閃亮沙子
        {
            "name": "pack_opening_result",
            "identifiers": get_text_patterns("pack_opening_result"),
            "priority": 99,
        },
        # 向上輕滑卡牌
        {
            "name": "pack_card_register",
            "identifiers": get_text_patterns("pack_card_register"),
            "priority": 99,
        },
        # 快进按钮
        {"name": "speed_up_button", "templates": ["btn_speed_up"], "priority": 99},
    ]


# ============================================================
# 统一开包流程基类
# ============================================================


class PackOpeningTaskBase(Task):
    """统一开包流程基类

    提供开包页面处理、卡牌识别、记录保存的统一实现。
    子类通过覆写扩展点方法实现差异化行为。
    """

    def __init__(self, adb, recognizer, page_detector):
        super().__init__(adb, recognizer, page_detector)

        # 初始化 YOLO+Hash 卡牌识别器
        self.card_recognizer = YoloCardRecognizer(
            adb=adb,
            model_manager=get_model_manager(),
            hash_manager=get_card_hash_manager(),
        )

        # 页面内操作缓存
        self._action_cache: dict[str, bool] = {}

        # 开包状态
        self._packs_opened_count = 0  # 本次任务已开包数量
        self._result_recognized = False  # 本次开包是否已识别结果

        # 数据仓储（延迟初始化）
        self._pack_record_repo: "PackRecordRepository | None" = None
        self._card_repo: "CardRepository | None" = None
        self._account_card_repo: "AccountCardRepository | None" = None
        self._pack_point_repo: "AccountPackPointRepository | None" = None

        # 子包推断会话状态（单次开包生命周期）
        self._inferred_pack_context: dict[str, str] | None = None

        # packs_auto 模板匹配器（会话级复用，任务结束统一卸载）
        self._pack_template_matcher: PackTemplateMatcher | None = None

    # ============================================================
    # 扩展点（子类覆写）
    # ============================================================

    def get_target_pack_context(self) -> dict[str, str] | None:
        """获取目标卡包上下文

        Returns:
            {"pack_code": str, "booster_name": str} 或 None
        """
        # 优先返回推断的上下文（如果没有显式目标）
        if self._inferred_pack_context:
            return self._inferred_pack_context
        return None

    def get_fixed_set_code(self) -> str | None:
        """获取固定的 set_code（优先于 context 中的 pack_code）

        Returns:
            固定的系列代码（如 "A1"）或 None
        """
        return None

    def should_prepare_pack_resources(self) -> bool:
        """是否需要准备卡包图片资源

        Returns:
            True 表示需要准备（如 open_pack 任务）
            False 表示不需要（如 claim_gifts、init_account）
        """
        return False

    @abstractmethod
    def get_pack_record_type(self) -> str:
        """获取 pack 记录类型

        Returns:
            记录类型："daily_free", "gift_box", "init_tutorial" 等

        Raises:
            NotImplementedError: 子类必须实现此方法
        """
        raise NotImplementedError("子类必须实现 get_pack_record_type 方法")

    @abstractmethod
    def get_rare_card_notify_message(self) -> str:
        """获取稀有卡通知消息（中文来源标记），如：开包获得稀有卡牌"""
        raise NotImplementedError("子类必须实现 get_rare_card_notify_message 方法")

    # ============================================================
    # 内部方法
    # ============================================================

    def _is_action_done(self, key: str) -> bool:
        """检查操作是否已完成"""
        return self._action_cache.get(key, False)

    def _mark_action_done(self, key: str):
        """标记操作已完成"""
        self._action_cache[key] = True

    def _reset_action_cache(self):
        """重置操作缓存（进入新页面时调用）"""
        self._action_cache.clear()

    def _init_repositories(self):
        """初始化数据仓储（如未初始化）"""
        if self._card_repo is not None:
            return

        from ptcgp_auto_v2.db.repositories import (
            AccountCardRepository,
            AccountPackPointRepository,
            CardRepository,
            PackRecordRepository,
        )

        self._account_card_repo = AccountCardRepository()
        self._pack_record_repo = PackRecordRepository()
        self._card_repo = CardRepository()
        self._pack_point_repo = AccountPackPointRepository()

    def _resolve_scan_set_code(self) -> str | None:
        """解析要使用的 set_code

        优先级：fixed_set_code > explicit_target.pack_code > inferred_context.pack_code > None
        注意：open_pack 的显式目标优先于推断上下文

        Returns:
            set_code 字符串或 None（全局模式）
        """
        # 1. 固定系列代码最高优先级
        if fixed := self.get_fixed_set_code():
            return fixed

        # 2. 显式目标上下文（如 open_pack 的 _target_pack）
        explicit_context = self.get_target_pack_context()
        if explicit_context and explicit_context.get("pack_code"):
            # 只有当显式上下文不是来自推断时才使用
            # 通过比较确认这不是推断上下文
            if explicit_context != self._inferred_pack_context:
                return explicit_context.get("pack_code")

        # 3. 推断上下文兜底
        return (self._inferred_pack_context or {}).get("pack_code")

    def _scan_cards_with_retry(
        self, set_code: str | None, max_retries: int
    ) -> list[DetectedCard]:
        """识别开包结果，失败时按固定次数重试

        Args:
            set_code: 系列代码，None 表示全局模式
            max_retries: 最大重试次数

        Returns:
            识别到的卡牌列表
        """
        for attempt in range(max_retries):
            try:
                # 开包扫描排除 PROMO 干扰，但保留普通系列下载能力
                cards = self.card_recognizer.scan(
                    set_code=set_code,
                    similarity_threshold=0.68,
                    debug=True,
                    exclude_promo=True,
                )
            except RuntimeError as e:
                logger.error(f"识别卡牌失败: {e}")
                cards = []

            if cards:
                return cards

            if attempt < max_retries - 1:
                logger.debug(f"未识别到卡牌，等待重试 ({attempt + 1}/{max_retries})")
                time.sleep(2.0)

        logger.warning(f"卡牌识别连续失败 {max_retries} 次，跳过识别")
        return []

    def _recognize_cards(self):
        """识别卡牌并保存记录（YOLO+Hash 版本）"""
        self._init_repositories()

        # 注意：None 表示全局识别模式，不兜底成 "Unknown"
        set_code = self._resolve_scan_set_code()
        cards = self._scan_cards_with_retry(set_code, max_retries=3)

        if not cards:
            self._result_recognized = True
            return

        if self._packs_opened_count == 0:
            self._packs_opened_count = 1

        # 使用 set_code 进行映射
        # set_code=None 表示全局模式，map_detected_cards 会使用每张卡自带的 set_code
        rows = map_detected_cards(
            cards=cards,
            card_repo=self._card_repo,
            fixed_set_code=set_code,
        )

        # 第二阶段：卡牌反推子包（仅在当前无目标包上下文时兜底）
        if self.get_target_pack_context() is None and rows:
            from ptcgp_auto_v2.db.models import Card

            cards = [
                row["card_obj"] for row in rows if isinstance(row.get("card_obj"), Card)
            ]
            inferred = infer_pack_by_cards(cards)
            if inferred:
                self._inferred_pack_context = inferred
                logger.info(
                    f"[子包推断-结果页] 反推识别: {inferred.get('pack_code')}/{inferred.get('booster_name') or '未确定'}"
                )

        self._save_pack_record(rows)

        if self._account_card_repo and self.account.id:
            self._save_high_rarity_cards(rows)
        logger.debug("==================================")
        self._result_recognized = True

    def _save_pack_record(self, rows: list[dict]) -> None:
        """保存本次开包记录到数据库"""
        self._init_repositories()

        if not (self._pack_record_repo and self.account.id):
            return

        try:
            context = self.get_target_pack_context() or {}
            set_code = context.get("pack_code")
            pack_name = context.get("booster_name")

            self._pack_record_repo.create_for_account(
                self.account.id,
                pack_type=self.get_pack_record_type(),
                pack_code=set_code,
                pack_name=pack_name,
                cards=rows,
            )
            card_names = [f"{row['card_name']}({row['rarity']})" for row in rows]
            logger.info(
                f"已保存开包记录: {set_code}/{pack_name} "
                f"({len(rows)} 张): {', '.join(card_names)}"
            )

        except Exception as e:
            logger.error(f"保存开包记录失败: {e}")
        finally:
            # 只清理推断上下文，模板在任务结束时统一清理
            self._inferred_pack_context = None
            logger.debug("[子包推断] 会话上下文已清理")

    def _save_high_rarity_cards(self, rows: list[dict]) -> None:
        """记录高稀有度卡牌并通知"""
        try:
            context = self.get_target_pack_context() or {}
            pack_name = context.get("booster_name")
            pack = (
                self._card_repo.get_pack_by_name(pack_name)
                if (self._card_repo is not None and pack_name)
                else None
            )
            save_high_rarity_cards(
                account_card_repo=self._account_card_repo,
                account_id=self.account.id,
                rows=rows,
                account=self.account,
                notifier=get_notifier(),
                notify_message=self.get_rare_card_notify_message(),
                pack=pack,
            )
        except Exception as e:
            logger.warning(f"保存高稀有度卡牌并通知失败: {e}")

    def _clear_pack_inference_session(self):
        """清理子包推断会话资源。

        清理推断上下文，并通过资源管理器卸载已加载模板。
        注意：此方法只在任务结束时调用，每包后只清理上下文不清模板。
        """
        try:
            matcher = getattr(self, "_pack_template_matcher", None)
            if matcher:
                matcher.end_session()
        except Exception as e:
            logger.warning(f"[子包推断] 清理模板资源失败: {e}")
        finally:
            self._inferred_pack_context = None
            logger.debug("[子包推断] 会话上下文已清理")

    def _preload_target_series_hash(self):
        """后台预加载目标系列 Hash"""
        set_code = self._resolve_scan_set_code()
        if not set_code:
            return

        def _preload():
            try:
                self.card_recognizer.hash_manager.ensure_series_ready(set_code)
                logger.debug(f"目标系列 {set_code} Hash 预加载完成")
            except Exception as e:
                logger.warning(f"预加载系列 {set_code} Hash 失败: {e}")

        threading.Thread(target=_preload, daemon=True).start()

    # ============================================================
    # 通用页面处理器
    # ============================================================

    def _handle_speed_up(self, page_info: dict) -> ActionResult:
        """处理快进按钮"""
        return tap_matched_element(self.adb, page_info, 0.5) or ActionResult.ok(
            wait=0.5
        )

    def _handle_opening_swipe(self, page_info: dict) -> ActionResult:
        """滑动开包。"""
        self._packs_opened_count += 1
        self._result_recognized = False

        if self.get_target_pack_context() is None:
            inferred = self._infer_pack_on_swipe()
            if inferred:
                self._inferred_pack_context = inferred
                logger.info(
                    f"[子包推断-滑动页] 识别到: {inferred.get('pack_code')}/{inferred.get('booster_name')}"
                )

        return swipe_open_pack(self.adb, wait=2.5)

    def _infer_pack_on_swipe(self) -> dict[str, str] | None:
        """第一阶段：滑动页模板推断。"""
        if not self._card_repo:
            self._init_repositories()

        if not self.recognizer:
            return None

        screenshot = self.adb.screenshot()
        if not screenshot:
            return None

        settings = get_settings()
        target_set_code = self._resolve_scan_set_code()

        if self._pack_template_matcher is None:
            self._pack_template_matcher = build_pack_template_matcher(self.recognizer)
        matcher = self._pack_template_matcher
        if matcher is None:
            return None

        candidates: list[PackCandidate] = []

        for pack in self._card_repo.get_all_packs() if self._card_repo else []:
            if target_set_code and pack.set_code != target_set_code:
                continue
            # 使用 set_code 过滤 PROMO，避免名称不是 "PROMO*"（如 "Vol. 1"）时误入候选
            if (pack.set_code or "").upper().startswith("PROMO"):
                continue
            if not pack.name or not pack.set_code:
                continue
            candidates.append(
                PackCandidate(set_code=str(pack.set_code), booster_name=str(pack.name))
            )

        best = matcher.match_best(
            screenshot,
            candidates,
            scale=settings.scale_pack_opening_swipe,
            threshold=settings.pack_template_threshold,
            exclude_promo=True,
            return_best_when_below_threshold=False,
        )
        if not best:
            return None

        return {
            "pack_code": best.candidate.set_code,
            "booster_name": best.candidate.booster_name,
            "source": "template",
        }

    def _handle_opening_card(self, page_info: dict) -> ActionResult:
        """长按跳过卡牌展示"""
        ocr_results = page_info.get("ocr_results", [])
        wait = 3.0
        result = long_press_opening_card(self.adb, ocr_results, wait=wait)
        if result:
            return result
        return ActionResult.ok(wait=wait)

    def _handle_pack_opening_select(self, page_info: dict) -> ActionResult:
        """点击选择要开的扩充包"""
        logger.debug("  -> 点击屏幕中心选择扩充包")
        return tap_center(self.adb, wait=1.0)

    def _handle_card_register(self, page_info: dict) -> ActionResult:
        """向上滑动卡牌登录图鉴"""
        logger.debug(f"  -> 向上滑动卡牌（已开 {self._packs_opened_count} 包）")
        return swipe_card_register(self.adb)

    def _handle_pack_opening_result(self, page_info: dict) -> ActionResult:
        """处理开包结果页：识别卡牌并点击继续"""
        if not self._result_recognized:
            self._recognize_cards()
        return tap_opening_continue(
            self.adb, page_info.get("ocr_results", []), wait=1.5
        )

    # ============================================================
    # 通用开包 Handler 自动分发
    # ============================================================

    def build_pack_opening_handlers(self) -> dict[str, Callable]:
        """构建通用开包页面处理器映射

        返回通用开包流程中所有页面的处理器字典。
        子类可在 handle_page 中通过以下方式合并：
            handlers = {**self.build_pack_opening_handlers(), **specific_handlers}

        Returns:
            dict: 页面名 -> 处理器方法的映射
        """
        return {
            "pack_opening_swipe": self._handle_opening_swipe,
            "pack_opening_select": self._handle_pack_opening_select,
            "pack_opening_card": self._handle_opening_card,
            "pack_card_register": self._handle_card_register,
            "pack_opening_result": self._handle_pack_opening_result,
            "speed_up_button": self._handle_speed_up,
        }

    def finalize_pack_session(self):
        """开包会话结束时的清理钩子

        子类应在任务结束（无论成功或异常）时调用此方法，
        确保动态模板和推断上下文被正确清理。
        """
        self._clear_pack_inference_session()
