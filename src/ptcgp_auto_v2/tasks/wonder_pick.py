# -*- coding: utf-8 -*-
"""
得卡挑战任务
"""

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
from ptcgp_auto_v2.core.task_base import ActionResult, ResetType, Task, TaskRegistry
from ptcgp_auto_v2.infra.card_hash_manager import get_card_hash_manager
from ptcgp_auto_v2.infra.icon_group_detector import IconGroupDetector, count_icons
from ptcgp_auto_v2.infra.model_manager import get_model_manager
from ptcgp_auto_v2.infra.notifier import get_notifier
from ptcgp_auto_v2.infra.yolo_card_recognizer import YoloCardRecognizer
from ptcgp_auto_v2.locales import get_text_patterns
from ptcgp_auto_v2.tasks.utils.card_pick import tap_favorite_card
from ptcgp_auto_v2.tasks.utils.high_rarity_saver import save_high_rarity_cards
from ptcgp_auto_v2.tasks.utils.pack_opening_flow import swipe_card_register
from ptcgp_auto_v2.tasks.utils.pack_result_mapper import (
    map_detected_cards,
)
from ptcgp_auto_v2.utils.card_name_resolver import resolve_card_name
from ptcgp_auto_v2.utils.gesture import (
    is_text_visible,
    navigate_back,
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

BASE_SCAN_SCROLL_DISTANCE_Y = 400  # 得卡挑战列表滚动距离（基准像素）
WONDER_PICK_SWIPE_STEPS = 8  # 得卡挑战滑动步数

WONDER_STAMINA_TEMPLATE = "icon_wonder_stamina"


def _build_challenge_pages() -> list[dict]:
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
        # 商店 / 得卡挑戰
        {
            "name": "game_home_main",
            "identifiers": get_text_patterns("game_home_main"),
            "match_all": True,
            "priority": 10,
        },
        # 向上輕滑卡牌
        {
            "name": "pack_card_register",
            "identifiers": get_text_patterns("pack_card_register"),
            "priority": 12,
        },
        # 得卡挑戰
        {
            "name": "card_challenge_list",
            "identifiers": get_text_patterns("card_challenge_title"),
            "exact_match": True,
            "priority": 20,
        },
        # GET!
        {
            "name": "card_challenge_get",
            "identifiers": get_text_patterns("card_challenge_get"),
            "exact_match": True,
            "priority": 40,
        },
    ]


@TaskRegistry.register("wonder_pick")
class WonderPickTask(Task):
    """得卡挑战任务"""

    task_type = "wonder_pick"
    reset_type = ResetType.DAILY
    max_iterations = 100
    max_unknown_pages = 20
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
        # 任务执行状态
        self._action_cache: dict[str, bool] = {}
        self._completed = False
        self._skipped = False

        # 挑战力状态
        self._current_stamina: Optional[int] = None
        self._stamina_zero_count = 0

        # 目标稀有度配置与选择
        self._target_rarities = self.sort_rarity_targets(WONDER_PICK_DEFAULT_TARGETS)
        self._cost_groups, self._cost_group_map = self._build_cost_groups(
            self._target_rarities
        )
        self._active_targets: list[str] = (
            self._cost_groups[0] if self._cost_groups else []
        )
        self._next_targets: list[str] = []

        # 列表扫描状态
        self._selected_rarity: Optional[str] = None
        self._last_signature: Optional[str] = None
        self._same_signature_count = 0
        self._target_pick_index: Optional[int] = None
        self._switching_targets = False
        self._switching_scroll_up = True

        # 页面流转控制
        self._force_reenter = False

        # 数据访问
        self._card_repo = None
        self._account_card_repo = None

    def _is_action_done(self, key: str) -> bool:
        return self._action_cache.get(key, False)

    def _mark_action_done(self, key: str):
        self._action_cache[key] = True

    def _reset_action_cache(self):
        self._action_cache.clear()

    def on_start(self):
        from ptcgp_auto_v2.db.repositories import AccountCardRepository, CardRepository

        self._card_repo = CardRepository()
        self._account_card_repo = AccountCardRepository()
        self._completed = False
        self._skipped = False
        self._current_stamina = None
        self._stamina_zero_count = 0
        self._active_targets = self._cost_groups[0] if self._cost_groups else []
        self._next_targets = []
        self._selected_rarity = None
        self._last_signature = None
        self._same_signature_count = 0
        self._target_pick_index = None
        self._force_reenter = False
        self._switching_targets = False
        self._switching_scroll_up = True
        self._reset_action_cache()

    def is_completed(self) -> bool:
        return self._completed or self._skipped

    def was_skipped(self) -> bool:
        return self._skipped

    def handle_page(self, page_name: str, page_info: dict) -> ActionResult:
        handlers = {
            "game_home_main": self._handle_home,
            "card_challenge_list": self._handle_list,
            "card_challenge_popup": self._handle_popup,
            "init_select_favorite_card": self._handle_select_favorite_card,
            "pack_card_register": self._handle_card_register,
            "card_challenge_get": self._handle_get_card,
            "popup_send_thanks": self._handle_send_thanks,
        }
        handler = handlers.get(page_name)
        if handler:
            return handler(page_info)
        return ActionResult.ok(wait=1.0)

    def handle_unknown_page(self, page_info) -> ActionResult:
        logger.debug("未知页面，等待后重试")
        return ActionResult.wait(0.5)

    def _handle_send_thanks(self, page_info: dict) -> ActionResult:
        """处理送出谢谢弹窗：点击"謝謝！"按钮"""
        ocr_results = page_info.get("ocr_results", [])
        thanks_patterns = get_text_patterns("thanks_button")

        result = tap_text_exact(self.adb, ocr_results, thanks_patterns, wait=1.5)
        if result:
            logger.debug("  -> 点击「謝謝！」按钮")
            return result

        logger.debug("  -> 未找到「謝謝！」按钮")
        return ActionResult.ok(wait=1.0)

    @staticmethod
    def sort_rarity_targets(targets: list[str]) -> list[str]:
        priority = {
            rarity: idx for idx, rarity in enumerate(WONDER_PICK_RARITY_PRIORITY)
        }
        valid = [rarity for rarity in targets if rarity in priority]
        return sorted(valid, key=lambda rarity: priority[rarity])

    @staticmethod
    def pick_best_target(found: list[str], targets: list[str]) -> Optional[str]:
        sorted_targets = WonderPickTask.sort_rarity_targets(targets)
        for rarity in sorted_targets:
            if rarity in found:
                return rarity
        return None

    @staticmethod
    def build_target_map(detected_cards, card_repo, targets: list[str]):
        target_set = set(targets)
        rarity_to_center: dict[str, tuple[float, float]] = {}
        found_rarities: list[str] = []
        if not detected_cards:
            return rarity_to_center, found_rarities
        for item in detected_cards:
            if not item.set_code:
                continue
            card = card_repo.get_card_by_set_and_number(item.set_code, item.card_number)
            if not card or not card.rarity:
                continue
            rarity = card.rarity
            if rarity not in target_set:
                continue
            if rarity in rarity_to_center:
                continue
            rarity_to_center[rarity] = item.center
            found_rarities.append(rarity)
        return rarity_to_center, found_rarities

    @staticmethod
    def pick_target_from_map(
        rarity_to_center: dict[str, tuple[float, float]], targets: list[str]
    ) -> Optional[tuple[str, tuple[float, float]]]:
        best = WonderPickTask.pick_best_target(list(rarity_to_center.keys()), targets)
        if not best:
            return None
        return best, rarity_to_center[best]

    @staticmethod
    def is_stamina_enough(stamina: int, rarity: str) -> bool:
        cost = WONDER_PICK_RARITY_COSTS.get(rarity)
        if cost is None:
            return False
        return stamina >= cost

    @staticmethod
    def has_end_marker(ocr_results: list[dict]) -> bool:
        return is_text_visible(
            ocr_results,
            get_text_patterns("card_challenge_end_already")
            + get_text_patterns("card_challenge_end_finished"),
            exact=True,
        )

    def _handle_home(self, page_info: dict) -> ActionResult:
        ocr_results = page_info.get("ocr_results", [])
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

        if self._should_end_due_to_stamina():
            self._completed = True
            return ActionResult.ok(wait=1.0)

        if self._force_reenter:
            result = tap_text_exact(
                self.adb,
                ocr_results,
                get_text_patterns("card_challenge_title"),
                wait=1.0,
            )
            if result:
                self._force_reenter = False
                return result
            return ActionResult.ok(wait=1.0)

        result = tap_text_exact(
            self.adb,
            ocr_results,
            get_text_patterns("card_challenge_title"),
            wait=1.0,
        )
        return result or ActionResult.ok(wait=1.0)

    def _handle_list(self, page_info: dict) -> ActionResult:
        ocr_results = page_info.get("ocr_results", [])

        if self._current_stamina is None:
            return navigate_back(
                self.adb,
                self.page_detector,
                ocr_results,
                get_text_patterns("back_button"),
            )

        if self._active_targets:
            logger.debug("当前寻找稀有度组: %s", "/".join(self._active_targets))

        if self._should_end_due_to_stamina():
            self._completed = True
            return navigate_back(
                self.adb,
                self.page_detector,
                ocr_results,
                get_text_patterns("back_button"),
            )

        detected = self._scan_cards()
        if self._update_scan_signature(detected) >= 3:
            if self._switching_targets:
                logger.info("切换目标中连续三次扫描一致，停止切换")
                self._switching_targets = False
            else:
                return self._handle_end_of_list("连续三次扫描结果一致")

        target = self._scan_targets(detected)
        if target:
            logger.info("命中目标稀有度: %s", target)
            self._selected_rarity = target
            if self._switching_targets:
                self._switching_targets = False
            return ActionResult.ok(wait=1.0)

        if self._switching_targets:
            direction = "向上" if self._switching_scroll_up else "向下"
            logger.info("切换目标中，继续%s滚动", direction)
            if self._switching_scroll_up:
                start, end = scroll_points(
                    self.adb,
                    base_distance_y=BASE_SCAN_SCROLL_DISTANCE_Y,
                    direction="down",
                )
            else:
                start, end = scroll_points(
                    self.adb,
                    base_distance_y=BASE_SCAN_SCROLL_DISTANCE_Y,
                    direction="up",
                )
            swipe(self.adb, start, end, steps=WONDER_PICK_SWIPE_STEPS, wait=0.8)
            return ActionResult.ok(wait=0.5)

        if self.has_end_marker(ocr_results):
            # 注意：当前逻辑不会在主页二次判断挑战力不足，
            # 若后续改动导致“已结束”不再触发任务结束，可能引发循环。
            return self._handle_end_of_list("已出现结束标志")

        start, end = scroll_points(
            self.adb, base_distance_y=BASE_SCAN_SCROLL_DISTANCE_Y, direction="up"
        )
        swipe(self.adb, start, end, steps=WONDER_PICK_SWIPE_STEPS, wait=0.8)
        return ActionResult.ok(wait=0.5)

    def _handle_popup(self, page_info: dict) -> ActionResult:
        ocr_results = page_info.get("ocr_results", [])
        if is_text_visible(
            ocr_results,
            get_text_patterns("card_challenge_recover"),
            exact=True,
        ):
            self._skip("挑战力不足")
            return ActionResult.ok(wait=1.0)

        # 在弹窗中重扫一次，确保目标位索引基于稳定的 5 张卡布局计算
        self._refresh_target_pick_index_in_popup()

        result = tap_ok(self.adb, ocr_results, wait=1.0)
        if result:
            self._consume_stamina()
            return result

        return ActionResult.ok(wait=0.5)

    def _handle_select_favorite_card(self, page_info: dict) -> ActionResult:
        """处理选择喜欢的卡牌页面"""
        logger.info("  -> 选择喜欢的卡牌")
        position = self._pick_random_card_position()
        if position:
            candidates = WONDER_PICK_RULES.get(
                self._target_pick_index or 0,
                list(WONDER_PICK_POSITIONS.keys()),
            )
            logger.info(
                "随机选卡: 目标位=%s, 候选位=%s, 最终点击坐标=(%s,%s)",
                self._target_pick_index,
                candidates,
                position[0],
                position[1],
            )
            self._target_pick_index = None
            return tap(self.adb, position[0], position[1], wait=1.0)
        return tap_favorite_card(self.adb, wait=1.0)

    def _handle_card_register(self, page_info: dict) -> ActionResult:
        """向上滑动卡牌登录图鉴（精英牌组奖励）"""
        return swipe_card_register(self.adb)

    def _handle_get_card(self, page_info: dict) -> ActionResult:
        ocr_results = page_info.get("ocr_results", [])
        if self._is_action_done("get_card_saved"):
            return self._navigate_back_from_get_card(ocr_results)

        if not self._card_repo or not self._account_card_repo or not self.account.id:
            return ActionResult.ok(wait=0.5)

        detected = self.card_recognizer.scan(
            debug=True,
            resolve_name=lambda set_code, card_number: resolve_card_name(
                self._card_repo, set_code, card_number
            ),
        )
        if not detected:
            return ActionResult.ok(wait=0.5)

        rows = map_detected_cards(
            cards=detected,
            card_repo=self._card_repo,
        )
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
        self._mark_action_done("get_card_saved")
        return self._navigate_back_from_get_card(ocr_results)

    def _navigate_back_from_get_card(self, ocr_results: list[dict]) -> ActionResult:
        """从 GET 页返回列表页。"""
        return navigate_back(
            self.adb,
            self.page_detector,
            ocr_results,
            get_text_patterns("back_button"),
        )

    def _scan_targets(self, detected=None) -> Optional[str]:
        if not self._card_repo:
            return None

        if detected is None:
            detected = self._scan_cards()
        if not detected:
            return None

        rarity_to_center, found_rarities = self.build_target_map(
            detected, self._card_repo, self._target_rarities
        )
        if not found_rarities:
            return None

        active_found = [r for r in self._active_targets if r in rarity_to_center]
        if active_found:
            best = self.pick_best_target(active_found, self._active_targets)
            if not best:
                return None
            center = rarity_to_center[best]
            self._tap_card_center(center)
            return best

        if not self._next_targets:
            best = self.pick_best_target(found_rarities, self._target_rarities)
            if best:
                next_group = self._cost_group_map.get(best, [best])
                self._next_targets = next_group
                logger.info("记录下一轮目标稀有度组: %s", "/".join(next_group))
        return None

    def _handle_end_of_list(self, reason: str) -> ActionResult:
        if self._next_targets:
            next_priority = self._get_group_priority(self._next_targets)
            current_priority = self._get_group_priority(self._active_targets)
            self._switching_scroll_up = next_priority >= current_priority
            direction = "向上" if self._switching_scroll_up else "向下"
            logger.info("命中结束标志，切换下一轮目标并%s滚动", direction)
            self._active_targets = self._next_targets
            self._next_targets = []
            self._last_signature = None
            self._same_signature_count = 0
            self._switching_targets = True
            if self._switching_scroll_up:
                start, end = scroll_points(
                    self.adb,
                    base_distance_y=BASE_SCAN_SCROLL_DISTANCE_Y,
                    direction="down",
                )
                return swipe(
                    self.adb,
                    start,
                    end,
                    wait=0.8,
                )
            start, end = scroll_points(
                self.adb, base_distance_y=BASE_SCAN_SCROLL_DISTANCE_Y, direction="up"
            )
            return swipe(
                self.adb,
                start,
                end,
                wait=0.8,
            )

        logger.info("结束得卡挑战扫描: %s", reason)
        self._completed = True
        return ActionResult.ok(wait=1.0)

    def _should_end_due_to_stamina(self) -> bool:
        if self._current_stamina is None:
            return False
        if not self._active_targets:
            return False
        active_cost = WONDER_PICK_RARITY_COSTS.get(self._active_targets[0])
        if active_cost is None:
            return False
        min_cost = min(
            WONDER_PICK_RARITY_COSTS.get(r, 99) for r in WONDER_PICK_DEFAULT_TARGETS
        )
        if self._current_stamina < active_cost:
            logger.info(
                "挑战力不足，结束得卡挑战任务: 当前=%s, 目标=%s/%s, 最低=%s",
                self._current_stamina,
                "/".join(self._active_targets),
                active_cost,
                min_cost,
            )
            return True
        return False

    def _build_rarity_index_map(self, detected) -> dict[str, int]:
        if not self._card_repo:
            return {}
        index_map: dict[str, int] = {}
        for idx, item in enumerate(detected, start=1):
            if not item.set_code:
                continue
            card = self._card_repo.get_card_by_set_and_number(
                item.set_code, item.card_number
            )
            if not card or not card.rarity:
                continue
            if card.rarity not in self._target_rarities:
                continue
            if card.rarity in index_map:
                continue
            index_map[card.rarity] = idx
        return index_map

    @staticmethod
    def _get_group_priority(group: list[str]) -> int:
        if not group:
            return 999
        priority = {
            rarity: idx for idx, rarity in enumerate(WONDER_PICK_RARITY_PRIORITY)
        }
        return min(priority.get(rarity, 999) for rarity in group)

    def _pick_random_card_position(self) -> Optional[tuple[int, int]]:
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

    @staticmethod
    def _build_cost_groups(
        targets: list[str],
    ) -> tuple[list[list[str]], dict[str, list[str]]]:
        groups: list[list[str]] = []
        cost_to_group: dict[int, list[str]] = {}
        rarity_to_group: dict[str, list[str]] = {}
        for rarity in targets:
            cost = WONDER_PICK_RARITY_COSTS.get(rarity)
            if cost is None:
                continue
            if cost not in cost_to_group:
                cost_to_group[cost] = []
                groups.append(cost_to_group[cost])
            cost_to_group[cost].append(rarity)
        for group in groups:
            for rarity in group:
                rarity_to_group[rarity] = group
        return groups, rarity_to_group

    def _update_scan_signature(self, detected) -> int:
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
        return self.card_recognizer.scan(
            debug=True,
            resolve_name=lambda set_code, card_number: resolve_card_name(
                self._card_repo, set_code, card_number
            ),
        )

    def _tap_card_center(self, center: tuple[float, float]):
        tap(self.adb, int(center[0]), int(center[1]), wait=0.5)

    def _consume_stamina(self):
        if self._current_stamina is None:
            return
        if not self._selected_rarity:
            return
        cost = WONDER_PICK_RARITY_COSTS.get(self._selected_rarity)
        if cost is None:
            return
        self._current_stamina = max(self._current_stamina - cost, 0)

    def _refresh_target_pick_index_in_popup(self):
        """在挑战确认弹窗内重扫卡牌，刷新目标位索引。"""
        self._target_pick_index = None
        if not self._selected_rarity or not self._card_repo:
            return

        detected = self._scan_cards()
        if not detected:
            return

        index_map = self._build_rarity_index_map(detected)
        self._target_pick_index = index_map.get(self._selected_rarity)
        logger.debug(
            "弹窗重扫目标位: rarity=%s, pick_index=%s",
            self._selected_rarity,
            self._target_pick_index,
        )

    def _get_wonder_stamina(self) -> Optional[int]:
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

    def _skip(self, reason: str):
        logger.info("得卡挑战任务跳过: %s", reason)
        self._skipped = True
        self._completed = True
