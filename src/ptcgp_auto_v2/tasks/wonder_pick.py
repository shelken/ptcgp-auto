# -*- coding: utf-8 -*-
"""得卡挑战任务。"""

import logging
import random
from typing import Optional

from ptcgp_auto_v2.config.wonder_pick import (
    WONDER_PICK_DEFAULT_TARGETS,
    WONDER_PICK_POSITIONS,
    WONDER_PICK_RARITY_COSTS,
    WONDER_PICK_RARITY_PRIORITY,
    WONDER_PICK_RULES,
)
from ptcgp_auto_v2.core.stateful_task import StatefulTask
from ptcgp_auto_v2.core.task_base import ActionResult, ResetType, TaskRegistry
from ptcgp_auto_v2.infra.card_hash_manager import get_card_hash_manager
from ptcgp_auto_v2.infra.icon_group_detector import IconGroupDetector, count_icons
from ptcgp_auto_v2.infra.model_manager import get_model_manager
from ptcgp_auto_v2.infra.notifier import get_notifier
from ptcgp_auto_v2.infra.yolo_card_recognizer import YoloCardRecognizer
from ptcgp_auto_v2.locales import get_text_patterns
from ptcgp_auto_v2.tasks.utils.card_pick import tap_favorite_card
from ptcgp_auto_v2.tasks.utils.constants import (
    BASE_PACK_RESULT_SCROLL_DISTANCE_Y,
    PACK_RESULT_SCROLL_SWIPE_STEPS,
)
from ptcgp_auto_v2.tasks.utils.high_rarity_saver import save_high_rarity_cards
from ptcgp_auto_v2.tasks.utils.pack_opening_flow import swipe_card_register
from ptcgp_auto_v2.tasks.utils.pack_result_mapper import map_detected_cards
from ptcgp_auto_v2.utils.card_name_resolver import resolve_card_name
from ptcgp_auto_v2.utils.gesture import (
    is_text_visible,
    navigate_back,
    quick_tap,
    scroll_points,
    swipe,
    tap,
    tap_ok,
    tap_text_exact,
)

logger = logging.getLogger(__name__)


# ============================================================
# 常量定义（基于 1080x1920 基准分辨率）
# ============================================================

WONDER_STAMINA_TEMPLATE = "icon_wonder_stamina"  # 挑战力图标模板


def _build_challenge_pages() -> list[dict]:
    """构建得卡挑战页面规则。"""
    return [
        # 剩餘遊玩次數
        {
            "name": "card_challenge_popup",
            "identifiers": get_text_patterns("card_challenge_remaining_plays"),
            "exact_match": False,
            "priority": 5,
        },
        # 選1張喜歡的卡牌吧
        {
            "name": "init_select_favorite_card",
            "identifiers": get_text_patterns("init_select_favorite_card"),
            "exact_match": True,
            "priority": 8,
        },
        # 要送出「謝謝！」嗎
        {
            "name": "popup_send_thanks",
            "identifiers": get_text_patterns("popup_send_thanks"),
            "priority": 9,
        },
        # 向上輕滑卡牌
        {
            "name": "pack_card_register",
            "identifiers": get_text_patterns("pack_card_register"),
            "priority": 12,
        },
        # 點擊來繼續
        {
            "name": "card_challenge_get",
            "identifiers": get_text_patterns("tap_to_continue"),
            "priority": 40,
            "exclude_identifiers": get_text_patterns("card_challenge_get_exclude"),
        },
        # 商店 / 得卡挑戰
        {
            "name": "game_home_main",
            "identifiers": get_text_patterns("game_home_main"),
            "match_all": True,
            "priority": 90,
        },
        # 得卡挑戰
        {
            "name": "card_challenge_list",
            "identifiers": get_text_patterns("card_challenge_title"),
            "exact_match": True,
            "priority": 91,
        },
    ]


@TaskRegistry.register("wonder_pick")
class WonderPickTask(StatefulTask):
    """得卡挑战任务。"""

    task_type = "wonder_pick"
    reset_type = ResetType.DAILY
    max_iterations = 250
    max_same_page_rounds = max_iterations
    pages = _build_challenge_pages()

    def __init__(self, adb, recognizer, page_detector):
        super().__init__(adb, recognizer, page_detector)
        self.icon_detector = IconGroupDetector(
            template_matcher=page_detector.template_matcher
        )
        self.card_recognizer = YoloCardRecognizer(
            adb=adb,
            model_manager=get_model_manager(),
            hash_manager=get_card_hash_manager(),
        )

        self._get_card_saved = False
        self._current_stamina: Optional[int] = None
        self._stamina_zero_count = 0

        self._target_rarities = self.sort_rarity_targets(WONDER_PICK_DEFAULT_TARGETS)
        self._cost_groups = self._build_cost_groups(self._target_rarities)
        self._active_targets: list[str] = []
        self._active_group_index: Optional[int] = None
        self._seen_lower_group_index: Optional[int] = None
        self._reverse_scan = False

        self._selected_rarity: Optional[str] = None
        self._target_pick_index: Optional[int] = None
        self._last_signature: Optional[str] = None
        self._same_signature_count = 0
        self._pending_after_challenge = False

        self._card_repo = None
        self._account_card_repo = None

    def on_start(self):
        """初始化任务运行状态。"""
        from ptcgp_auto_v2.db.repositories import AccountCardRepository, CardRepository

        self.state.reset()
        self._card_repo = CardRepository()
        self._account_card_repo = AccountCardRepository()
        self._get_card_saved = False
        self._current_stamina = None
        self._stamina_zero_count = 0
        self._active_targets = []
        self._active_group_index = None
        self._seen_lower_group_index = None
        self._reverse_scan = False
        self._selected_rarity = None
        self._target_pick_index = None
        self._last_signature = None
        self._same_signature_count = 0
        self._pending_after_challenge = False

    def handle_unknown_page(self, page_info) -> ActionResult:
        """未知页面等待。"""
        logger.debug("未知页面，点击屏幕上方兜底")
        return quick_tap(self.adb, self.adb.center_x(), self.adb.scaled_y(10))

    @staticmethod
    def sort_rarity_targets(targets: list[str]) -> list[str]:
        """按稀有度优先级排序。"""
        priority = {
            rarity: idx for idx, rarity in enumerate(WONDER_PICK_RARITY_PRIORITY)
        }
        valid = [rarity for rarity in targets if rarity in priority]
        return sorted(valid, key=lambda rarity: priority[rarity])

    @staticmethod
    def pick_best_target(found: list[str], targets: list[str]) -> Optional[str]:
        """从命中的目标中选择最高优先级。"""
        priority = {
            rarity: idx for idx, rarity in enumerate(WONDER_PICK_RARITY_PRIORITY)
        }
        valid = [rarity for rarity in targets if rarity in priority]
        sorted_targets = sorted(valid, key=lambda rarity: priority[rarity])
        for rarity in sorted_targets:
            if rarity in found:
                return rarity
        return None

    @staticmethod
    def is_stamina_enough(stamina: int, rarity: str) -> bool:
        """判断当前挑战力是否足够。"""
        cost = WONDER_PICK_RARITY_COSTS.get(rarity)
        if cost is None:
            return False
        return stamina >= cost

    @staticmethod
    def has_end_marker(ocr_results: list[dict]) -> bool:
        """判断列表页是否出现结束标记。"""
        return is_text_visible(
            ocr_results,
            get_text_patterns("card_challenge_end_already")
            + get_text_patterns("card_challenge_end_finished"),
            exact=True,
        )

    @staticmethod
    def _build_cost_groups(targets: list[str]) -> list[list[str]]:
        """按挑战力消耗将目标稀有度分组。"""
        groups: list[list[str]] = []
        cost_to_group: dict[int, list[str]] = {}
        for rarity in targets:
            cost = WONDER_PICK_RARITY_COSTS.get(rarity)
            if cost is None:
                continue
            if cost not in cost_to_group:
                cost_to_group[cost] = []
                groups.append(cost_to_group[cost])
            cost_to_group[cost].append(rarity)
        return groups

    def _refresh_active_targets(self):
        """按当前挑战力刷新当前可挑战的目标组。"""
        self._active_targets = []
        self._active_group_index = None
        self._seen_lower_group_index = None
        self._reverse_scan = False
        if self._current_stamina is None:
            return
        for index, group in enumerate(self._cost_groups):
            if group and self.is_stamina_enough(self._current_stamina, group[0]):
                self._active_targets = list(group)
                self._active_group_index = index
                return

    def _handle_game_home_main(self, page_info: dict) -> ActionResult:
        """主页读取挑战力并进入得卡挑战。"""
        if not self._target_rarities:
            self._skip("未配置目标稀有度")
            return ActionResult.ok(wait=1.0)

        stamina = self._get_wonder_stamina()
        if stamina is None:
            logger.debug("未识别到挑战力图标，稍后重试")
            return ActionResult.ok(wait=1.0)

        if stamina == 0:
            self._stamina_zero_count += 1
            logger.debug("挑战力识别为0，等待重试(%s/3)", self._stamina_zero_count)
            if self._stamina_zero_count < 3:
                return ActionResult.ok(wait=1.0)
        else:
            self._stamina_zero_count = 0

        self._current_stamina = stamina
        self._refresh_active_targets()
        if not self._active_targets:
            self.complete()
            return ActionResult.ok(wait=1.0)

        result = tap_text_exact(
            self.adb,
            page_info.get("ocr_results", []),
            get_text_patterns("card_challenge_title"),
            wait=1.0,
        )
        return result or ActionResult.ok(wait=1.0)

    def _handle_card_challenge_list(self, page_info: dict) -> ActionResult:
        """列表页：只扫当前挑战力组。"""
        if self._current_stamina is None:
            return navigate_back(
                self.adb,
                self.page_detector,
                page_info.get("ocr_results", []),
            )

        if self._pending_after_challenge:
            self._selected_rarity = None
            self._target_pick_index = None
            self._get_card_saved = False
            self._refresh_active_targets()
            self._reset_scan_round()
            self._pending_after_challenge = False

        if not self._active_targets:
            self.complete()
            return ActionResult.ok(wait=1.0)

        detected = self._scan_cards()
        target = self._pick_target_on_current_page(detected)
        if target:
            logger.info("命中目标稀有度: %s", target)
            self._selected_rarity = target
            return ActionResult.ok(wait=1.0)

        if not self._reverse_scan:
            self._record_seen_lower_group(detected)

        if self._should_finish_current_group(
            detected,
            page_info.get("ocr_results", []),
        ):
            return self._advance_scan_group()

        return self._scroll_list(direction="down" if self._reverse_scan else "up")

    def _pick_target_on_current_page(self, detected) -> Optional[str]:
        """在当前页当前组内选择目标卡并点击。"""
        page_targets = self._collect_page_targets(detected)
        if not page_targets:
            return None

        active_found = [
            rarity for rarity, _ in page_targets if rarity in self._active_targets
        ]
        if not active_found:
            return None

        best = self.pick_best_target(active_found, self._active_targets)
        if not best:
            return None

        for rarity, center in page_targets:
            if rarity == best:
                self._tap_card_center(center)
                return best
        return None

    def _collect_page_targets(self, detected) -> list[tuple[str, tuple[float, float]]]:
        """收集当前页所有目标卡及其坐标。"""
        if not self._card_repo or not detected:
            return []

        rows = map_detected_cards(cards=detected, card_repo=self._card_repo)
        page_targets: list[tuple[str, tuple[float, float]]] = []
        for item, row in zip(detected, rows):
            rarity = row.get("rarity")
            if not rarity or rarity not in self._target_rarities:
                continue
            page_targets.append((rarity, item.center))
        return page_targets

    def _should_finish_current_group(
        self,
        detected,
        ocr_results: list[dict],
    ) -> bool:
        """判断当前组是否已经扫到结束。"""
        if not self._reverse_scan and self.has_end_marker(ocr_results):
            return True
        return self._update_scan_signature(detected) >= 3

    def _advance_scan_group(self) -> ActionResult:
        """当前组结束后切换到已见的次优先级组；否则结束。"""
        if self._reverse_scan:
            self.complete()
            return ActionResult.ok(wait=1.0)

        if self._seen_lower_group_index is None:
            self.complete()
            return ActionResult.ok(wait=1.0)

        group = self._cost_groups[self._seen_lower_group_index]
        self._active_targets = list(group)
        self._active_group_index = self._seen_lower_group_index
        self._seen_lower_group_index = None
        self._reverse_scan = True
        self._reset_scan_round()
        logger.info("切换到下一目标组: %s", "/".join(group))
        return self._scroll_list(direction="down")

    def _record_seen_lower_group(self, detected):
        """记录本轮向下扫描中见过的最高优先级更低目标组。"""
        if self._active_group_index is None:
            return

        page_targets = self._collect_page_targets(detected)
        if not page_targets:
            return

        found_rarities = {rarity for rarity, _ in page_targets}
        for index in range(self._active_group_index + 1, len(self._cost_groups)):
            group = self._cost_groups[index]
            if any(rarity in found_rarities for rarity in group):
                if (
                    self._seen_lower_group_index is None
                    or index < self._seen_lower_group_index
                ):
                    self._seen_lower_group_index = index
                return

    def _handle_card_challenge_popup(self, page_info: dict) -> ActionResult:
        """挑战确认弹窗。"""
        ocr_results = page_info.get("ocr_results", [])
        if is_text_visible(
            ocr_results,
            get_text_patterns("card_challenge_recover"),
            exact=True,
        ):
            self._skip("挑战力不足")
            return ActionResult.ok(wait=1.0)

        self._refresh_target_pick_index_in_popup()
        result = tap_ok(self.adb, ocr_results, wait=1.0)
        if result:
            self._get_card_saved = False
            self._consume_stamina()
            self._pending_after_challenge = True
            return result
        return ActionResult.ok(wait=0.5)

    def _handle_init_select_favorite_card(self, page_info: dict) -> ActionResult:
        """随机选取卡牌。"""
        position = self._pick_random_card_position()
        if position:
            self._target_pick_index = None
            return tap(self.adb, position[0], position[1], wait=1.0)
        return tap_favorite_card(self.adb, wait=1.0)

    def _handle_pack_card_register(self, page_info: dict) -> ActionResult:
        """处理图鉴登录页。"""
        return swipe_card_register(self.adb)

    def _handle_card_challenge_get(self, page_info: dict) -> ActionResult:
        """GET/结果页保存高稀有度卡并继续推进。"""
        ocr_results = page_info.get("ocr_results", [])
        if not self._get_card_saved:
            if (
                not self._card_repo
                or not self._account_card_repo
                or not self.account.id
            ):
                return ActionResult.ok(wait=0.5)

            detected = self.card_recognizer.scan(
                resolve_name=lambda set_code, card_number: resolve_card_name(
                    self._card_repo,
                    set_code,
                    card_number,
                ),
            )
            if not detected:
                return ActionResult.ok(wait=0.5)

            rows = map_detected_cards(cards=detected, card_repo=self._card_repo)
            if not any(row.get("card_id") for row in rows):
                return ActionResult.ok(wait=0.5)

            save_high_rarity_cards(
                account_card_repo=self._account_card_repo,
                account_id=self.account.id,
                rows=rows,
                account=self.account,
                notifier=get_notifier(),
                notify_message="得卡挑战获得稀有卡牌",
            )
            self._get_card_saved = True

        result = tap_text_exact(
            self.adb,
            ocr_results,
            get_text_patterns("tap_to_continue"),
            wait=1.0,
        )
        if result:
            return result

        result = tap_text_exact(
            self.adb,
            ocr_results,
            get_text_patterns("continue_button"),
            wait=1.0,
        )
        return result or ActionResult.ok(wait=0.5)

    def _handle_popup_send_thanks(self, page_info: dict) -> ActionResult:
        """处理谢谢弹窗。"""
        result = tap_text_exact(
            self.adb,
            page_info.get("ocr_results", []),
            get_text_patterns("thanks_button"),
            wait=1.5,
        )
        return result or ActionResult.ok(wait=0.5)

    def _scroll_list(self, direction: str, wait: float = 0.6) -> ActionResult:
        """滚动得卡挑战列表。"""
        start, end = scroll_points(
            self.adb,
            base_distance_y=BASE_PACK_RESULT_SCROLL_DISTANCE_Y,
            direction=direction,
        )
        swipe(self.adb, start, end, steps=PACK_RESULT_SCROLL_SWIPE_STEPS, wait=wait)
        return ActionResult.ok(wait=0.4)

    def _update_scan_signature(self, detected) -> int:
        """更新当前页识别签名，连续相同用于判定到底。"""
        signature = self._build_card_signature(detected)
        if not signature:
            return self._same_signature_count
        if self._last_signature == signature:
            self._same_signature_count += 1
        else:
            self._same_signature_count = 1
            self._last_signature = signature
        return self._same_signature_count

    @staticmethod
    def _build_card_signature(detected) -> Optional[str]:
        """构建当前页识别卡牌签名。"""
        if not detected:
            return None
        signature_items = []
        for item in detected:
            if not item.set_code:
                continue
            signature_items.append(f"{item.set_code}:{item.card_number}")
        if not signature_items:
            return None
        return "|".join(sorted(signature_items))

    def _scan_cards(self):
        """扫描当前页卡牌。"""
        return self.card_recognizer.scan(
            resolve_name=lambda set_code, card_number: resolve_card_name(
                self._card_repo,
                set_code,
                card_number,
            ),
        )

    def _tap_card_center(self, center: tuple[float, float]):
        """点击目标卡片中心。"""
        tap(self.adb, int(center[0]), int(center[1]), wait=0.5)

    def _consume_stamina(self):
        """按本次命中的目标稀有度扣减挑战力，并刷新下一轮目标组。"""
        if self._current_stamina is None or not self._selected_rarity:
            return
        cost = WONDER_PICK_RARITY_COSTS.get(self._selected_rarity)
        if cost is None:
            return
        self._current_stamina = max(self._current_stamina - cost, 0)
        self._refresh_active_targets()
        self._reset_scan_round()

    def _pick_random_card_position(self) -> Optional[tuple[int, int]]:
        """根据目标位索引生成随机点击位置。"""
        if self._target_pick_index in WONDER_PICK_RULES:
            candidates = WONDER_PICK_RULES[self._target_pick_index]
        else:
            candidates = list(WONDER_PICK_POSITIONS.keys())
        if not candidates:
            return None
        chosen = random.choice(candidates)
        position = WONDER_PICK_POSITIONS.get(chosen)
        if not position:
            return None
        return self.adb.scaled_x(position[0]), self.adb.scaled_y(position[1])

    def _refresh_target_pick_index_in_popup(self):
        """在确认弹窗内读取目标位索引。"""
        self._target_pick_index = None
        if not self._selected_rarity or not self._card_repo:
            return
        detected = self._scan_cards()
        if not detected:
            return

        rows = map_detected_cards(cards=detected, card_repo=self._card_repo)
        for idx, row in enumerate(rows, start=1):
            if row.get("rarity") == self._selected_rarity:
                self._target_pick_index = idx
                return

    def _get_wonder_stamina(self) -> Optional[int]:
        """统计主页挑战力图标数量。"""
        screenshot, _ = self.page_detector.get_last_page_context()
        if screenshot is None:
            screenshot, _ = self.page_detector.capture()
        if screenshot is None:
            return None

        hits = self.icon_detector.detect_icons(
            screenshot=screenshot,
            template_paths={"icon_wonder_stamina": WONDER_STAMINA_TEMPLATE},
            threshold=0.8,
            nms_iou=0.3,
            screen_width=self.adb.screen_width,
        )
        return count_icons("icon_wonder_stamina", hits)

    def _reset_scan_round(self):
        """重置一轮列表扫描状态。"""
        self._last_signature = None
        self._same_signature_count = 0

    def _skip(self, reason: str):
        """跳过并结束任务。"""
        logger.info("得卡挑战任务跳过: %s", reason)
        self.skip(reason)
