# -*- coding: utf-8 -*-
"""选卡扫描稳定计数与滚动测试。"""

from types import MethodType, SimpleNamespace
from unittest.mock import MagicMock

import ptcgp_auto_v2.tasks.exchange_cards as exchange_cards_module
import ptcgp_auto_v2.tasks.send_card_daily as send_card_daily_module
from ptcgp_auto_v2.core.task_base import ActionResult
from ptcgp_auto_v2.tasks.exchange_cards import ExchangeCardsTask
from ptcgp_auto_v2.tasks.send_card_daily import SendCardDailyTask
from ptcgp_auto_v2.tasks.utils.friend_card_flow import (
    CardScanScrollState,
    advance_card_scan_scroll_state,
    scroll_card_list,
)


def _card(set_code: str, number: int):
    return SimpleNamespace(set_code=set_code, card_number=number)


class _Adb:
    def center_x(self):
        return 540

    def center_y(self):
        return 960

    def scaled_y(self, value: int):
        return value


def test_card_scan_state_resets_when_signature_changes():
    """扫描结果变化时重置稳定轮数，并记录新的签名。"""
    state = CardScanScrollState(last_signature="A1:1", stable_rounds=2)

    next_state, reached_limit = advance_card_scan_scroll_state(
        [_card("A1", 2)],
        state,
    )

    assert next_state == CardScanScrollState(last_signature="A1:2", stable_rounds=0)
    assert reached_limit is False


def test_card_scan_state_increments_when_signature_is_same():
    """扫描结果连续不变时累加稳定轮数。"""
    state = CardScanScrollState(last_signature="A1:1", stable_rounds=1)

    next_state, reached_limit = advance_card_scan_scroll_state(
        [_card("A1", 1)],
        state,
    )

    assert next_state == CardScanScrollState(last_signature="A1:1", stable_rounds=2)
    assert reached_limit is False


def test_card_scan_state_reports_limit_on_third_stable_round():
    """连续三轮相同扫描结果后触发未找到目标卡失败分支。"""
    state = CardScanScrollState(last_signature="A1:1", stable_rounds=2)

    next_state, reached_limit = advance_card_scan_scroll_state(
        [_card("A1", 1)],
        state,
    )

    assert next_state == CardScanScrollState(last_signature="A1:1", stable_rounds=3)
    assert reached_limit is True


def test_scroll_card_list_can_return_original_swipe_result(monkeypatch):
    """送卡保持直接返回 swipe 结果，wait 使用 1.4。"""
    calls = []
    swipe_result = ActionResult.ok(wait=1.4)

    monkeypatch.setattr(
        "ptcgp_auto_v2.tasks.utils.friend_card_flow.scroll_points",
        lambda adb, base_distance_y, direction: ((10, 900), (10, 400)),
    )
    monkeypatch.setattr(
        "ptcgp_auto_v2.tasks.utils.friend_card_flow.swipe",
        lambda adb, start, end, wait: calls.append((start, end, wait)) or swipe_result,
    )

    result = scroll_card_list(_Adb(), wait_scroll=1.4, return_swipe_result=True)

    assert result is swipe_result
    assert calls == [((10, 900), (10, 400), 1.4)]


def test_scroll_card_list_can_return_wait_after_result(monkeypatch):
    """交换保持 swipe 后返回独立等待结果。"""
    calls = []

    monkeypatch.setattr(
        "ptcgp_auto_v2.tasks.utils.friend_card_flow.scroll_points",
        lambda adb, base_distance_y, direction: ((10, 900), (10, 400)),
    )
    monkeypatch.setattr(
        "ptcgp_auto_v2.tasks.utils.friend_card_flow.swipe",
        lambda adb, start, end, wait: calls.append((start, end, wait)) or ActionResult.ok(wait=0.8),
    )

    result = scroll_card_list(_Adb(), wait_scroll=0.8, wait_after=0.6)

    assert result.success is True
    assert result.should_wait == 0.6
    assert calls == [((10, 900), (10, 400), 0.8)]


def test_send_card_select_card_scrolls_with_original_wait(monkeypatch):
    """送卡未找到目标卡时调用共享滚动 helper，并直接返回 swipe 结果。"""
    state = {
        "filter_applied": True,
        "last_card_signature": None,
        "card_stable_rounds": 0,
    }
    calls = []
    task = SendCardDailyTask.__new__(SendCardDailyTask)
    task.adb = _Adb()
    task.card_recognizer = SimpleNamespace(scan=lambda set_code: [])
    task._tap_target_card_by_scan = lambda detected: None
    task.state_get = MethodType(lambda self, key, default=None: state.get(key, default), task)
    task.state_set = MethodType(lambda self, key, value: state.__setitem__(key, value), task)
    task.is_action_done = MethodType(lambda self, key: False, task)

    monkeypatch.setattr(
        send_card_daily_module,
        "scroll_card_list",
        lambda adb, wait_scroll, return_swipe_result: calls.append(
            (adb, wait_scroll, return_swipe_result)
        )
        or ActionResult.ok(wait=1.4),
    )

    result = task._handle_select_card({})

    assert result.should_wait == 1.4
    assert calls == [(task.adb, 1.4, True)]
    assert state["last_card_signature"] == "__EMPTY__"
    assert state["card_stable_rounds"] == 0


def test_exchange_select_card_scrolls_with_original_wait(monkeypatch):
    """交换未找到目标卡时调用共享滚动 helper，并返回交换自己的等待结果。"""
    calls = []
    task = ExchangeCardsTask.__new__(ExchangeCardsTask)
    task.adb = _Adb()
    task._card_recognizer = SimpleNamespace(scan=lambda set_code: [])
    task._tap_target_card = lambda detected: None
    task._req = MethodType(lambda self: object(), task)
    task.state_get = MethodType(
        lambda self, key, default=None: "A1" if key == "card_set_code" else default,
        task,
    )
    task.is_action_done = MethodType(
        lambda self, key: key in {"filter_opened", "filter_applied"},
        task,
    )
    task._last_card_signature = None
    task._card_stable_rounds = 0

    monkeypatch.setattr(
        exchange_cards_module,
        "scroll_card_list",
        lambda adb, wait_scroll, wait_after: calls.append((adb, wait_scroll, wait_after))
        or ActionResult.ok(wait=wait_after),
    )

    result = task._handle_exchange_select_card({"ocr_results": []})

    assert result.should_wait == 0.6
    assert calls == [(task.adb, 0.8, 0.6)]
    assert task._last_card_signature == "__EMPTY__"
    assert task._card_stable_rounds == 0


def test_send_card_select_card_skips_when_empty_scan_reaches_stable_limit(monkeypatch):
    """送卡连续三次空扫描后以无卡状态跳过，不再继续滚动。"""
    state = {
        "filter_applied": True,
        "last_card_signature": "__EMPTY__",
        "card_stable_rounds": 2,
    }
    skip_calls = []
    task = SendCardDailyTask.__new__(SendCardDailyTask)
    task.adb = _Adb()
    task.card_recognizer = SimpleNamespace(scan=lambda set_code: [])
    task._tap_target_card_by_scan = lambda detected: None
    task.state_get = MethodType(lambda self, key, default=None: state.get(key, default), task)
    task.state_set = MethodType(lambda self, key, value: state.__setitem__(key, value), task)
    task.is_action_done = MethodType(lambda self, key: False, task)
    task._skip_without_send = MethodType(
        lambda self, **kwargs: skip_calls.append(kwargs) or ActionResult.ok(wait=0.3),
        task,
    )
    scroll_card_list_mock = MagicMock()

    monkeypatch.setattr(send_card_daily_module, "scroll_card_list", scroll_card_list_mock)

    result = task._handle_select_card({})

    assert result.success is True
    assert skip_calls == [
        {
            "skip_reason": "扫描多次未找到目标卡 A1-153，结束本次送卡任务",
            "record_status": "completed_no_card",
            "error_code": "CARD_NOT_FOUND_BY_SCAN",
        }
    ]
    scroll_card_list_mock.assert_not_called()


def test_exchange_select_card_fails_when_empty_scan_reaches_stable_limit(monkeypatch):
    """交换连续三次空扫描后失败，不再继续滚动。"""
    fail_calls = []
    task = ExchangeCardsTask.__new__(ExchangeCardsTask)
    task.adb = _Adb()
    task._card_recognizer = SimpleNamespace(scan=lambda set_code: [])
    task._tap_target_card = lambda detected: None
    task._req = MethodType(lambda self: object(), task)
    task.state_get = MethodType(
        lambda self, key, default=None: "A1" if key == "card_set_code" else default,
        task,
    )
    task.is_action_done = MethodType(
        lambda self, key: key in {"filter_opened", "filter_applied"},
        task,
    )
    task._fail = MethodType(
        lambda self, message: fail_calls.append(message) or ActionResult.ok(wait=0.3),
        task,
    )
    task._last_card_signature = "__EMPTY__"
    task._card_stable_rounds = 2
    scroll_card_list_mock = MagicMock()

    monkeypatch.setattr(exchange_cards_module, "scroll_card_list", scroll_card_list_mock)

    result = task._handle_exchange_select_card({"ocr_results": []})

    assert result.success is True
    assert fail_calls == ["连续三次扫描未找到目标卡牌"]
    scroll_card_list_mock.assert_not_called()


def test_send_card_select_card_updates_record_status_when_scan_taps_target(monkeypatch):
    """送卡扫描命中并点卡后，将记录推进到已选卡。"""
    state = {"filter_applied": True, "record_id": 42}
    update_status_calls = []
    tap_result = ActionResult.ok(wait=3.5)
    task = SendCardDailyTask.__new__(SendCardDailyTask)
    task.adb = _Adb()
    task.card_recognizer = SimpleNamespace(scan=lambda set_code: [object()])
    task._tap_target_card_by_scan = lambda detected: tap_result
    task.state_get = MethodType(lambda self, key, default=None: state.get(key, default), task)
    task.state_set = MethodType(lambda self, key, value: state.__setitem__(key, value), task)
    task.is_action_done = MethodType(lambda self, key: False, task)

    monkeypatch.setattr(
        send_card_daily_module.GiftRecordService,
        "update_status",
        lambda record_id, **kwargs: update_status_calls.append((record_id, kwargs)),
    )

    result = task._handle_select_card({})

    assert result is tap_result
    assert update_status_calls == [(42, {"status": "card_selected"})]


def test_exchange_select_card_marks_card_tapped_and_resets_scan_state():
    """交换扫描命中并点卡后标记动作完成，同时清空稳定计数状态。"""
    action_done_calls = []
    tap_result = ActionResult.ok(wait=3.5)
    task = ExchangeCardsTask.__new__(ExchangeCardsTask)
    task.adb = _Adb()
    task._card_recognizer = SimpleNamespace(scan=lambda set_code: [object()])
    task._tap_target_card = lambda detected: tap_result
    task._req = MethodType(lambda self: object(), task)
    task.state_get = MethodType(
        lambda self, key, default=None: "A1" if key == "card_set_code" else default,
        task,
    )
    task.is_action_done = MethodType(
        lambda self, key: key in {"filter_opened", "filter_applied"},
        task,
    )
    task.mark_action_done = MethodType(
        lambda self, key: action_done_calls.append(key),
        task,
    )
    task._last_card_signature = "A1:153"
    task._card_stable_rounds = 2

    result = task._handle_exchange_select_card({"ocr_results": []})

    assert result is tap_result
    assert action_done_calls == ["card_tapped"]
    assert task._card_stable_rounds == 0
    assert task._last_card_signature is None
