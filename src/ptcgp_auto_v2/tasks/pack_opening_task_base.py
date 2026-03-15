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

import json
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
from ptcgp_auto_v2.tasks.utils.constants import (
    BASE_PACK_RESULT_SCROLL_DISTANCE_Y,
    PACK_RESULT_SCROLL_SWIPE_STEPS,
)
from ptcgp_auto_v2.tasks.utils.high_rarity_saver import save_high_rarity_cards
from ptcgp_auto_v2.tasks.utils.pack_opening_flow import (
    swipe_card_register,
    swipe_open_pack,
    tap_opening_continue,
)
from ptcgp_auto_v2.tasks.utils.pack_result_mapper import PackResultMapper
from ptcgp_auto_v2.tasks.utils.pack_result_rows import (
    BASE_COMMON_CARD_X_TOLERANCE,
    build_pack_groups,
    build_row_signature,
    group_rows,
    has_incomplete_rows,
    merge_or_append_rows,
)
from ptcgp_auto_v2.tasks.utils.pack_template_matcher import (
    PackCandidate,
    PackTemplateMatcher,
    build_pack_template_matcher,
)
from ptcgp_auto_v2.utils.gesture import (
    quick_tap,
    scroll_points,
    swipe,
    tap_center,
    tap_matched_element,
)
from ptcgp_auto_v2.utils.pack_image_manager import PackImageManager

if TYPE_CHECKING:
    from ptcgp_auto_v2.db.repositories import (
        AccountCardRepository,
        AccountPackPointRepository,
        CardRepository,
        PackRecordRepository,
    )

logger = logging.getLogger(__name__)


PACK_RESULT_MODE_SINGLE = "single"
PACK_RESULT_MODE_TEN = "ten"
PACK_RESULT_ROWS_PER_PACK = 2
OPENING_CARD_QUICK_TAP_TIMES = 6
OPENING_CARD_WAIT = 3.0
OPENING_CARD_TEN_FAST_TAP_LIMIT = 10


# ============================================================
# 通用开包页面规则构建
# ============================================================


def build_pack_opening_pages() -> list[dict]:
    """构建开包流程通用页面规则

    包含开包过程中的标准页面：
    - 横向滑动开包
    - 长按开包卡牌
    - 十包总览结果
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
        # 十包总览结果（第1包/第2包/.../继续）
        {
            "name": "pack_opening_multi_result",
            "identifiers": get_text_patterns("pack_opening_multi_result"),
            "exact_match": True,
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
        self._base_pack_points: int | None = None  # 从OCR提取的基础开包点数
        self._pack_result_mode = PACK_RESULT_MODE_SINGLE
        self._pack_result_batch_size = 1
        self._pack_result_rows: list[list[dict]] = []
        self._multi_pack_swipe_counted = False
        self._opening_card_tap_count = 0
        self._pack_result_mapper: PackResultMapper | None = None
        self._current_batch_id: str | None = None  # 当前十连包批次ID

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
            {"set_code": str, "booster_name": str} 或 None
        """
        # 优先返回推断的上下文（如果没有显式目标）
        if self._inferred_pack_context:
            return self._inferred_pack_context
        return None

    def get_fixed_set_code(self) -> str | None:
        """获取固定的 set_code（优先于 context 中的 set_code）

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
            记录类型：daily_free、ten_pack、gift_box、init_tutorial 等

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
        from ptcgp_auto_v2.db.repositories import (
            AccountCardRepository,
            AccountPackPointRepository,
            CardRepository,
            PackRecordRepository,
        )

        if self._account_card_repo is None:
            self._account_card_repo = AccountCardRepository()
        if self._pack_record_repo is None:
            self._pack_record_repo = PackRecordRepository()
        if self._card_repo is None:
            self._card_repo = CardRepository()
        if self._pack_point_repo is None:
            self._pack_point_repo = AccountPackPointRepository()
        if self._pack_result_mapper is None:
            self._pack_result_mapper = PackResultMapper(self._card_repo)

    def _get_pack_result_mapper(self) -> PackResultMapper:
        """获取统一的开包结果映射器。"""
        self._init_repositories()
        return self._pack_result_mapper

    def _resolve_scan_set_code(self) -> str | None:
        """解析要使用的 set_code

        优先级：fixed_set_code > explicit_target.set_code > inferred_context.set_code > None
        注意：open_pack 的显式目标优先于推断上下文

        Returns:
            set_code 字符串或 None（全局模式）
        """
        # 1. 固定系列代码最高优先级
        if fixed := self.get_fixed_set_code():
            return fixed

        # 2. 显式目标上下文（如 open_pack 的 _target_pack）
        explicit_context = self.get_target_pack_context()
        if explicit_context and explicit_context.get("set_code"):
            # 只有当显式上下文不是来自推断时才使用
            # 通过比较确认这不是推断上下文
            if explicit_context != self._inferred_pack_context:
                return explicit_context.get("set_code")

        # 3. 推断上下文兜底
        return (self._inferred_pack_context or {}).get("set_code")

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

        # 使用 set_code 进行映射；set_code=None 时由映射器使用每张卡自带的 set_code
        rows = self._get_pack_result_mapper().map_detected_cards(
            cards=cards,
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
                    f"[子包推断-结果页] 反推识别: {inferred.get('set_code')}/{inferred.get('booster_name') or '未确定'}"
                )

        self._save_pack_record(rows)

        if self._account_card_repo and self.account.id:
            self._save_high_rarity_cards(rows)
        self._result_recognized = True

    def _save_pack_record(self, rows: list[dict], batch_index: int | None = None) -> None:
        """保存本次开包记录到数据库，并根据开包数量累加开包点数

        Args:
            rows: 卡牌行数据
            batch_index: 批次内序号，十连包为1-10
        """
        self._init_repositories()

        if not (self._pack_record_repo and self.account.id):
            return

        try:
            context = self.get_target_pack_context() or {}
            set_code = context.get("set_code")
            pack_name = context.get("booster_name")

            self._pack_record_repo.create_for_account(
                self.account.id,
                pack_type=self.get_pack_record_type(),
                set_code=set_code,
                pack_name=pack_name,
                cards=rows,
                batch_id=self._current_batch_id,
                batch_index=batch_index,
            )
            card_names = [
                f"{self._resolve_log_card_name(row)}({row['rarity']})" for row in rows
            ]
            logger.info(
                f"已保存开包记录: {set_code}/{pack_name} "
                f"({len(rows)} 张): {', '.join(card_names)}"
            )

            # 根据开包数量累加开包点数（仅 open_pack 任务：基础点数 + 开包数 × 5）
            if (
                set_code
                and self._pack_point_repo
                and self._base_pack_points is not None
            ):
                final_points = self._base_pack_points + self._packs_opened_count * 5
                self._pack_point_repo.upsert_points(
                    self.account.id, set_code, final_points
                )
                logger.info(
                    f"  -> 更新开包点数: {set_code} = {final_points}pt (基础 {self._base_pack_points}pt + 开包 {self._packs_opened_count} 包 × 5pt)"
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
        if self._pack_result_mode == PACK_RESULT_MODE_TEN:
            if not self._multi_pack_swipe_counted:
                self._packs_opened_count += self._pack_result_batch_size
                self._multi_pack_swipe_counted = True
        else:
            self._packs_opened_count += 1
        self._result_recognized = False

        if self.get_target_pack_context() is None:
            inferred = self._infer_pack_on_swipe()
            if inferred:
                self._inferred_pack_context = inferred
                logger.info(
                    f"[子包推断-滑动页] 识别到: {inferred.get('set_code')}/{inferred.get('booster_name')}"
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
            "set_code": best.candidate.set_code,
            "booster_name": best.candidate.booster_name,
            "source": "template",
        }

    def _handle_opening_card(self, page_info: dict) -> ActionResult:
        """长按跳过卡牌展示"""
        wait = OPENING_CARD_WAIT
        if self._pack_result_mode == PACK_RESULT_MODE_TEN:
            self._opening_card_tap_count += 1
            if self._opening_card_tap_count <= OPENING_CARD_TEN_FAST_TAP_LIMIT:
                wait = 0.0
            else:
                wait = OPENING_CARD_WAIT

        return quick_tap(
            self.adb,
            y=self.adb.center_y(),
            times=OPENING_CARD_QUICK_TAP_TIMES,
            wait=wait,
        )

    def _handle_pack_opening_select(self, page_info: dict) -> ActionResult:
        """点击选择要开的扩充包"""
        logger.info("  -> 点击屏幕中心选择扩充包")
        return tap_center(self.adb, wait=1.0)

    def _handle_card_register(self, page_info: dict) -> ActionResult:
        """向上滑动卡牌登录图鉴"""
        logger.debug(f"  -> 向上滑动卡牌（已开 {self._packs_opened_count} 包）")
        return swipe_card_register(self.adb)

    def _handle_pack_opening_result(self, page_info: dict) -> ActionResult:
        """处理开包结果页：识别卡牌并点击继续"""
        if not self._result_recognized:
            if self._pack_result_mode == PACK_RESULT_MODE_TEN:
                if not self._recognize_multi_pack_results():
                    return ActionResult.ok(wait=1.0)
            else:
                self._recognize_cards()
        if not self._result_recognized:
            return ActionResult.ok(wait=1.0)
        return tap_opening_continue(
            self.adb, page_info.get("ocr_results", []), wait=1.5
        )

    def _set_pack_result_mode(self, batch_size: int = 1) -> None:
        """设置当前开包结果模式。"""
        import uuid

        resolved_batch_size = max(1, batch_size)
        self._pack_result_batch_size = resolved_batch_size
        self._pack_result_mode = (
            PACK_RESULT_MODE_TEN if resolved_batch_size > 1 else PACK_RESULT_MODE_SINGLE
        )
        self._pack_result_rows = []
        self._multi_pack_swipe_counted = False
        self._opening_card_tap_count = 0
        # 多包模式下生成批次ID
        if resolved_batch_size > 1:
            # 测试环境下可能没有绑定账号，使用随机ID
            try:
                account_id = self.account.id if self.account else "test"
            except RuntimeError:
                account_id = "test"
            self._current_batch_id = f"{account_id}_{uuid.uuid4().hex[:12]}"
        else:
            self._current_batch_id = None

    def _reset_pack_result_mode(self) -> None:
        """重置当前开包结果模式为单包默认值。"""
        self._set_pack_result_mode()
        self._current_batch_id = None

    def _group_result_rows(self, cards: list[DetectedCard]) -> list[list[dict]]:
        """将单屏识别结果转换为按行分组的卡牌列表。"""
        mapped_cards = self._get_pack_result_mapper().map_detected_cards(
            cards=cards,
            fixed_set_code=self._resolve_scan_set_code(),
        )
        row_threshold = self.adb.scaled_y(self.card_recognizer.BASE_ROW_THRESHOLD)
        return group_rows(mapped_cards, row_threshold=row_threshold)

    @staticmethod
    def _resolve_log_card_name(card: dict) -> str:
        """解析日志中的卡牌名称，优先中文，缺失时回退现有名称。"""
        card_obj = card.get("card_obj")
        raw_data = getattr(card_obj, "data", None) if card_obj else None
        if raw_data:
            try:
                payload = (
                    json.loads(raw_data) if isinstance(raw_data, str) else raw_data
                )
                localized = (
                    payload.get("localized_name") if isinstance(payload, dict) else None
                )
                zh_name = localized.get("zh") if isinstance(localized, dict) else None
                if zh_name:
                    return str(zh_name)
            except Exception:
                pass
        fallback_name = card.get("card_name")
        if fallback_name:
            return str(fallback_name)
        signature = build_row_signature([card])
        return signature[0] if signature else "Unknown"

    @staticmethod
    def _format_result_row(row: list[dict] | None) -> str:
        """格式化结果行日志。"""
        if not row:
            return "[]"
        names = [PackOpeningTaskBase._resolve_log_card_name(card) for card in row]
        return "[" + ", ".join(names) + "]"

    def _log_multi_pack_rows_snapshot(self) -> None:
        """打印当前已收集的全部结果行，便于调试分组问题。"""
        logger.debug(
            "10包结果页当前逻辑行快照: 共 %s/%s 行",
            len(self._pack_result_rows),
            self._pack_result_batch_size * PACK_RESULT_ROWS_PER_PACK,
        )
        for index, row in enumerate(self._pack_result_rows, start=1):
            logger.debug(
                "  行%02d (%s张): %s",
                index,
                len(row),
                self._format_result_row(row),
            )

    def _collect_multi_pack_rows(self) -> bool:
        """滚动结果页并收集 10 包的全部逻辑行。"""
        expected_rows = self._pack_result_batch_size * PACK_RESULT_ROWS_PER_PACK
        previous_screen_signature: list[tuple[str, ...]] | None = None

        while True:
            cards = self._scan_cards_with_retry(
                self._resolve_scan_set_code(),
                max_retries=3,
            )
            incoming_rows = self._group_result_rows(cards)
            current_screen_signature = [
                tuple(build_row_signature(row)) for row in incoming_rows
            ]
            stats = merge_or_append_rows(
                self._pack_result_rows,
                incoming_rows,
                x_tolerance=self.adb.scaled_x(BASE_COMMON_CARD_X_TOLERANCE),
            )
            for decision in stats.get("decisions", []):
                logger.debug(
                    "  -> 结果行策略=%s incoming=%s matched=%s result=%s",
                    decision["action"],
                    self._format_result_row(decision.get("incoming_row")),
                    self._format_result_row(decision.get("matched_row")),
                    self._format_result_row(decision.get("result_row")),
                )

            is_complete = (
                len(self._pack_result_rows) >= expected_rows
                and not has_incomplete_rows(self._pack_result_rows)
            )
            if is_complete:
                break

            if current_screen_signature == previous_screen_signature:
                break
            previous_screen_signature = current_screen_signature

            start, end = scroll_points(
                self.adb,
                base_distance_y=BASE_PACK_RESULT_SCROLL_DISTANCE_Y,
                direction="up",
            )
            swipe(
                self.adb,
                start,
                end,
                steps=PACK_RESULT_SCROLL_SWIPE_STEPS,
                wait=0.0,
            )
            time.sleep(1.0)

        return (
            len(self._pack_result_rows) == expected_rows
            and not has_incomplete_rows(self._pack_result_rows)
        )

    def _recognize_multi_pack_results(self) -> bool:
        """识别 10 包结果页并拆成多条独立开包记录。"""
        self._init_repositories()

        try:
            collected = self._collect_multi_pack_rows()
            self._log_multi_pack_rows_snapshot()
            if not collected:
                logger.warning(
                    "10包结果页收集不完整: 期望 %s 行，实际 %s 行",
                    self._pack_result_batch_size * PACK_RESULT_ROWS_PER_PACK,
                    len(self._pack_result_rows),
                )
                return False

            pack_groups = build_pack_groups(
                self._pack_result_rows,
                rows_per_pack=PACK_RESULT_ROWS_PER_PACK,
            )
            if len(pack_groups) != self._pack_result_batch_size:
                logger.warning(
                    "10包结果页分组失败: 期望 %s 包，实际 %s 包",
                    self._pack_result_batch_size,
                    len(pack_groups),
                )
                return False

            for idx, rows in enumerate(pack_groups, start=1):
                self._save_pack_record(rows, batch_index=idx)
                if self._account_card_repo and self.account.id:
                    self._save_high_rarity_cards(rows)

            self._result_recognized = True
            return True
        finally:
            self._reset_pack_result_mode()

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
            "pack_opening_multi_result": self._handle_pack_opening_result,
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
