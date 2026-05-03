# -*- coding: utf-8 -*-
"""任务奖励页主题收藏决策测试。"""

import ptcgp_auto_v2.tasks.claim_rewards as claim_rewards_module
from ptcgp_auto_v2.core.task_base import ActionResult
from ptcgp_auto_v2.tasks.claim_rewards import ClaimRewardsTask


class _PageDetector:
    def __init__(self, screenshot, ocr_results):
        self._screenshot = screenshot
        self._ocr_results = ocr_results

    def get_last_page_context(self):
        return self._screenshot, self._ocr_results


def _ocr(text: str) -> dict:
    return {"text": text, "box": (10, 10, 100, 40)}


def _task(
    claim_all_clickable: bool,
    ocr_results: list[dict] | None = None,
) -> ClaimRewardsTask:
    task = ClaimRewardsTask.__new__(ClaimRewardsTask)
    state: dict[str, object] = {}
    task.adb = object()
    task.page_detector = _PageDetector(object(), ocr_results or [])
    task.state_get = lambda key, default=None: state.get(key, default)
    task.state_set = lambda key, value: state.__setitem__(key, value)
    task._is_claim_all_clickable = lambda box, screenshot: claim_all_clickable
    return task


def test_green_claim_all_skips_theme_collection():
    """全部领取为绿色时，当前 Tab 自己处理，不进入主题收藏。"""
    task = _task(claim_all_clickable=True)

    assert not task._needs_theme_collection([_ocr("全部領取")], object())


def test_gray_claim_all_checks_theme_collection():
    """全部领取置灰时，需要进入主题收藏。"""
    task = _task(claim_all_clickable=False)

    assert task._needs_theme_collection([_ocr("全部領取")], object())


def test_exact_claim_button_skips_theme_collection():
    """精确出现领取时，当前 Tab 自己处理，不进入主题收藏。"""
    task = _task(claim_all_clickable=False)

    assert not task._needs_theme_collection([_ocr("領取")], object())


def test_no_claim_entry_checks_theme_collection():
    """没有全部领取也没有领取时，需要进入主题收藏。"""
    task = _task(claim_all_clickable=False)

    assert task._needs_theme_collection([_ocr("每日任務")], object())


def test_click_claim_buttons_still_taps_claim_all_when_gray(monkeypatch):
    """全部领取置灰时，仍先尝试点击全部领取与领取。"""
    task = _task(
        claim_all_clickable=False,
        ocr_results=[_ocr("全部領取"), _ocr("領取"), _ocr("主題收藏")],
    )
    tapped_patterns: list[tuple[str, ...]] = []

    def fake_tap_text(adb, ocr_results, patterns, wait=0.0, exact=True):
        tapped_patterns.append(tuple(patterns))
        return ActionResult.ok(wait=wait)

    monkeypatch.setattr(claim_rewards_module, "tap_text", fake_tap_text)

    assert task._click_claim_buttons(task.page_detector._ocr_results, object())
    assert tapped_patterns == [("全部領取",), ("領取", "達成", "達成！")]


def test_rewards_page_attempts_claim_before_theme_collection(monkeypatch):
    """奖励页先尝试领取，再决定是否进入主题收藏。"""
    task = _task(
        claim_all_clickable=False,
        ocr_results=[_ocr("全部領取"), _ocr("領取"), _ocr("主題收藏")],
    )
    call_order: list[str] = []

    def fake_click_claim_buttons(ocr_results, screenshot):
        call_order.append("claim")
        return False

    def fake_needs_theme_collection(ocr_results, screenshot):
        call_order.append("theme-check")
        return True

    def fake_tap_text(adb, ocr_results, patterns, wait=0.0, exact=True):
        call_order.append("theme-tap")
        return ActionResult.ok(wait=wait)

    task._click_claim_buttons = fake_click_claim_buttons
    task._needs_theme_collection = fake_needs_theme_collection
    monkeypatch.setattr(claim_rewards_module, "tap_text", fake_tap_text)

    result = task._handle_rewards_page({})

    assert result.should_wait == 2.0
    assert call_order == ["claim", "theme-check", "theme-tap"]


def test_rewards_page_enters_theme_collection_after_claiming_current_tab(monkeypatch):
    """当前 Tab 点过领取后，下轮先处理主题收藏，不直接关闭。"""
    task = _task(
        claim_all_clickable=False,
        ocr_results=[_ocr("全部領取"), _ocr("主題收藏")],
    )
    task.state_set("claimed_current_rewards_tab", True)
    call_order: list[str] = []

    def fake_needs_theme_collection(ocr_results, screenshot):
        call_order.append("theme-check")
        return True

    def fake_tap_text(adb, ocr_results, patterns, wait=0.0, exact=True):
        call_order.append("theme-tap")
        return ActionResult.ok(wait=wait)

    def fail_if_leave_rewards_page(ocr_results):
        raise AssertionError("不应在主题收藏前关闭任务页")

    task._needs_theme_collection = fake_needs_theme_collection
    task._leave_rewards_page = fail_if_leave_rewards_page
    monkeypatch.setattr(claim_rewards_module, "tap_text", fake_tap_text)

    result = task._handle_rewards_page({})

    assert result.should_wait == 2.0
    assert call_order == ["theme-check", "theme-tap"]


def test_rewards_page_closes_after_returning_from_theme_collection(monkeypatch):
    """从主题收藏返回后，奖励页直接关闭，不再点击主题收藏。"""
    task = _task(claim_all_clickable=False, ocr_results=[_ocr("主題收藏")])
    task.state_set("claimed_current_rewards_tab", True)
    task.state_set("returned_from_theme_collection", True)
    expected = ActionResult.ok(wait=0.5)
    call_order: list[str] = []

    def fake_tap_text(adb, ocr_results, patterns, wait=0.0, exact=True):
        call_order.append("theme-tap")
        return ActionResult.ok(wait=wait)

    task._leave_rewards_page = lambda ocr_results: expected
    monkeypatch.setattr(claim_rewards_module, "tap_text", fake_tap_text)

    result = task._handle_rewards_page({})

    assert result is expected
    assert call_order == []
