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
from typing import TYPE_CHECKING

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
    infer_pack_by_templates,
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
from ptcgp_auto_v2.utils.card_naming import normalize_name_str
from ptcgp_auto_v2.utils.gesture import (
    quick_tap,
    tap_center,
    tap_matched_element,
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

    # 通用开包页面规则（与任务特定页面合并）
    pack_opening_pages: list[dict] = []

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

        # 数据仓储（延迟加载）
        self._pack_record_repo: "PackRecordRepository | None" = None
        self._card_repo: "CardRepository | None" = None
        self._pack_point_repo: "AccountPackPointRepository | None" = None
        self._account_card_repo: "AccountCardRepository | None" = None

        # 子包推断会话状态（单次开包生命周期）
        self._inferred_pack_context: dict[str, str] | None = None
        self._loaded_dynamic_pack_templates: list[str] = []

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
        """初始化数据仓储"""
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

        # 第二阶段：卡牌反推子包（兜底）
        if self._inferred_pack_context is None and rows:
            inferred = self._infer_pack_by_cards(rows)
            if inferred:
                self._inferred_pack_context = inferred
                logger.info(
                    f"[子包推断-结果页] 反推识别: {inferred.get('pack_code')}/{inferred.get('booster_name') or '未确定'}"
                )

        current_batch_cards = [
            {
                "card_name": row.get("card_name"),
                "rarity": row.get("rarity"),
                "card_id": row.get("card_id"),
                "is_new": bool(row.get("is_new", False)),
                "position": row.get("position"),
                "confidence": float(row.get("confidence") or 0.0),
                "hash_similarity": float(row.get("hash_similarity") or 0.0),
            }
            for row in rows
        ]

        self._save_pack_record(current_batch_cards)

        if self._account_card_repo and self.account.id:
            self._save_high_rarity_cards(rows)
        logger.debug("==================================")
        self._result_recognized = True

    def _infer_pack_by_cards(self, rows: list[dict]) -> dict[str, str] | None:
        """通过卡牌反推子包（第二阶段兜底）。

        Args:
            rows: 识别到的卡牌行数据，每项包含 set_code, card_id

        Returns:
            {"pack_code": str, "booster_name": str|None, "source": "cards"}
            或 None（无法确定）
        """
        if not self._card_repo:
            self._init_repositories()

        if not rows:
            return None

        try:
            # 构建 detected_rows 格式
            detected_rows = [
                {"set_code": row.get("set_code"), "card_id": row.get("card_id")}
                for row in rows
                if row.get("set_code") and row.get("card_id")
            ]

            if not detected_rows:
                return None

            # 获取所有卡牌ID
            card_ids = [row["card_id"] for row in detected_rows]

            # 批量获取卡牌子包关系（排除 PROMO）
            card_pack_mapping = self._card_repo.get_card_pack_names_batch(
                card_ids, exclude_promo=True
            )

            # 获取系列子包映射
            set_codes = list(set(row["set_code"] for row in detected_rows))
            pack_names_by_set = {}
            for set_code in set_codes:
                packs = self._card_repo.get_pack_names_by_set(
                    set_code, exclude_promo=True
                )
                if packs:
                    pack_names_by_set[set_code] = packs

            result = infer_pack_by_cards(
                detected_rows=detected_rows,
                pack_names_by_set=pack_names_by_set,
                card_pack_mapping=card_pack_mapping,
            )

            return result

        except Exception as e:
            logger.warning(f"[子包推断-结果页] 反推失败: {e}")
            return None

    def _save_pack_record(self, current_batch_cards: list[dict]) -> None:
        """保存本次开包记录到数据库"""
        if not (self._pack_record_repo and self.account.id):
            return

        try:
            context = self.get_target_pack_context() or {}
            pack_code = context.get("pack_code")
            pack_name = context.get("booster_name")

            self._pack_record_repo.create_for_account(
                self.account.id,
                pack_type=self.get_pack_record_type(),
                pack_code=pack_code,
                pack_name=pack_name,
                cards=current_batch_cards,
            )
            card_names = [
                f"{card['card_name']}({card['rarity']})" for card in current_batch_cards
            ]
            logger.info(
                f"已保存开包记录: {pack_code}/{pack_name} "
                f"({len(current_batch_cards)} 张): {', '.join(card_names)}"
            )

        except Exception as e:
            logger.error(f"保存开包记录失败: {e}")
        finally:
            # 无论成功与否都清理推断会话
            self._clear_pack_inference_session()

    def _save_high_rarity_cards(self, rows: list[dict]) -> None:
        """记录高稀有度卡牌并通知"""
        try:
            save_high_rarity_cards(
                account_card_repo=self._account_card_repo,
                account_id=self.account.id,
                rows=rows,
                account=self.account,
                notifier=get_notifier(),
                notify_message=self.get_rare_card_notify_message(),
            )
        except Exception as e:
            logger.warning(f"保存高稀有度卡牌并通知失败: {e}")

    def _clear_pack_inference_session(self):
        """清理子包推断会话资源。

        卸载动态加载的模板并清理推断上下文。
        在落库成功后调用，防止模板常驻内存。
        """
        try:
            template_matcher = self.recognizer[1] if self.recognizer else None
            if template_matcher and self._loaded_dynamic_pack_templates:
                template_matcher.unload_templates(self._loaded_dynamic_pack_templates)
                logger.debug(
                    f"[子包推断] 已卸载 {len(self._loaded_dynamic_pack_templates)} 个动态模板"
                )
                self._loaded_dynamic_pack_templates.clear()

            self._inferred_pack_context = None
            logger.debug("[子包推断] 会话上下文已清理")
        except Exception as e:
            logger.warning(f"[子包推断] 清理会话资源失败: {e}")

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
        """滑动开包（第一阶段：模板推断）"""
        self._packs_opened_count += 1
        self._result_recognized = False

        # 仅在无子包上下文时尝试推断
        if self._inferred_pack_context is None:
            inferred = self._try_infer_pack_on_swipe()
            if inferred:
                self._inferred_pack_context = inferred
                logger.info(
                    f"[子包推断-滑动页] 识别到: {inferred.get('pack_code')}/{inferred.get('booster_name')}"
                )

        return swipe_open_pack(self.adb, wait=2.5)

    def _try_infer_pack_on_swipe(self) -> dict[str, str] | None:
        """在滑动页尝试通过模板匹配推断子包（第一阶段）。

        流程：
        1. 从仓储获取所有非 PROMO 子包作为候选
        2. 批量加载 packs_auto 模板（仅加载一次）
        3. 在当前页面做多尺度匹配
        4. 返回最佳匹配的子包信息

        Returns:
            {"pack_code": str, "booster_name": str, "source": "template", "score": float}
            或 None（无有效匹配）
        """
        if not self._card_repo:
            self._init_repositories()

        try:
            # 获取所有非 PROMO 子包作为候选
            all_packs = self._card_repo.get_all_packs() if self._card_repo else []
            candidates = []
            for pack in all_packs:
                if pack.name.upper().startswith("PROMO"):
                    continue
                # 规范化模板文件名，避免空格/符号导致加载失败
                normalized_name = normalize_name_str(pack.name)
                candidates.append(
                    {
                        "pack_code": pack.set_code,
                        "booster_name": pack.name,
                        "template": f"packs_auto/{normalized_name}",
                    }
                )

            if not candidates:
                logger.debug("[子包推断] 无可用候选子包")
                return None

            # 批量加载模板（仅加载一次）
            template_matcher = self.recognizer[1] if self.recognizer else None
            if not template_matcher:
                logger.debug("[子包推断] 模板匹配器不可用")
                return None

            if not self._loaded_dynamic_pack_templates:
                for candidate in candidates:
                    template_name = candidate["template"]
                    if template_matcher.load_template(template_name + ".png"):
                        self._loaded_dynamic_pack_templates.append(template_name)

                if not self._loaded_dynamic_pack_templates:
                    logger.debug("[子包推断] 无法加载任何模板")
                    return None

                logger.debug(
                    f"[子包推断] 已加载 {len(self._loaded_dynamic_pack_templates)} 个模板"
                )

            # 截图并多尺度匹配
            screenshot = self.adb.screenshot()
            if not screenshot:
                return None

            def matcher_fn(template_name: str) -> dict | None:
                # 尝试多尺度匹配
                for scale in [0.95, 1.0, 1.05]:
                    match = template_matcher.find_with_scale(
                        screenshot, template_name, scale, threshold=0.60
                    )
                    if match:
                        return {"score": match.confidence, "box": match.box}
                return None

            result = infer_pack_by_templates(
                candidate_templates=candidates,
                matcher_fn=matcher_fn,
                threshold=0.65,
            )

            return result

        except Exception as e:
            logger.warning(f"[子包推断-滑动页] 推断失败: {e}")
            return None

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

    def _handle_unknown_pack_page(self, page_info) -> ActionResult:
        """开包流程中的未知页面兜底"""
        logger.debug("未知页面，点击屏幕上方兜底")
        return quick_tap(self.adb, self.adb.center_x(), self.adb.scaled_y(10), times=3)

    # ============================================================
    # 通用开包 Handler 自动分发
    # ============================================================

    def build_pack_opening_handlers(self) -> dict[str, callable]:
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

    # ============================================================
    # 子类可覆写的钩子
    # ============================================================

    def on_pack_opening_start(self):
        """开包流程开始前的钩子

        子类可覆写以执行额外的初始化逻辑。
        """
        pass

    def on_pack_record_saved(self, cards: list[dict]):
        """开包记录保存后的钩子

        Args:
            cards: 已保存的卡牌列表
        """
        pass

    def finalize_pack_session(self):
        """开包会话结束时的清理钩子

        子类应在任务结束（无论成功或异常）时调用此方法，
        确保动态模板和推断上下文被正确清理。
        """
        self._clear_pack_inference_session()
