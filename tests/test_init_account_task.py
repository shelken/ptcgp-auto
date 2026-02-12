# -*- coding: utf-8 -*-

from ptcgp_auto_v2.locales import get_text_patterns
from ptcgp_auto_v2.tasks import init_account
from ptcgp_auto_v2.tasks.init_account import InitAccountPhase, InitAccountTask
from ptcgp_auto_v2.utils.action_result import ActionResult


class _DummyAdb:
    """最小化 ADB 替身，仅用于单元测试。"""

    def center_x(self) -> int:
        return 540

    def scaled_y(self, value: int) -> int:
        return value

    def scaled_x(self, value: int) -> int:
        return value


def test_select_country_should_open_list_when_only_year_month_hint_visible(monkeypatch):
    """仅出现“年/月”提示文案时，仍应先点击“國家/地區”打开国家列表。"""

    task = InitAccountTask(adb=_DummyAdb(), recognizer=None, page_detector=object())

    ocr_results = [
        {"text": "選擇國家/地區", "box": [0, 0, 100, 50]},
        {"text": "請選擇您的出生年/月", "box": [0, 0, 100, 50]},
        {"text": "年齡確認", "box": [0, 0, 100, 50]},
        {"text": "國家/地區", "box": [0, 0, 100, 50]},
        {"text": "OK", "box": [0, 0, 100, 50]},
    ]

    called = {"country_btn": 0}

    def _fake_tap_text_exact(adb, ocr, patterns, wait=1.0):
        if patterns == get_text_patterns("init_country_btn"):
            called["country_btn"] += 1
            return ActionResult.ok(wait=wait)
        return None

    monkeypatch.setattr(init_account, "tap_text_exact", _fake_tap_text_exact)
    monkeypatch.setattr(init_account, "tap_ok", lambda adb, ocr, wait=1.0: None)

    task._handle_select_country({"ocr_results": ocr_results})

    assert called["country_btn"] == 1
    assert task._is_action_done("select_country_list_opened") is True


def test_select_country_should_not_reset_country_clicked_on_main_form(monkeypatch):
    """主表单已显示已选国家时，点击 OK 后不应清空国家已选状态。"""

    task = InitAccountTask(adb=_DummyAdb(), recognizer=None, page_detector=object())
    task._mark_action_done("select_country_list_opened")
    task._mark_action_done("select_country_country_clicked")

    ocr_results = [
        {"text": "選擇國家/地區", "box": [0, 0, 100, 50]},
        {"text": "請選擇您居住的國家/地區", "box": [0, 0, 100, 50]},
        {"text": "香港", "box": [0, 0, 100, 50]},
        {"text": "2005", "box": [0, 0, 100, 50]},
        {"text": "2", "box": [0, 0, 100, 50]},
        {"text": "OK", "box": [0, 0, 100, 50]},
    ]

    monkeypatch.setattr(
        init_account, "tap_text_exact", lambda adb, ocr, patterns, wait=1.0: None
    )
    monkeypatch.setattr(
        init_account, "tap_ok", lambda adb, ocr, wait=1.0: ActionResult.ok(wait=wait)
    )

    task._handle_select_country({"ocr_results": ocr_results})

    assert task._is_action_done("select_country_country_clicked") is True


def test_handle_page_should_not_complete_on_home_without_favorite_card_marker():
    """未完成“喜欢卡牌”阶段时，进入主页不应直接判定初始化完成。"""

    task = InitAccountTask(adb=_DummyAdb(), recognizer=None, page_detector=object())

    result = task.handle_page("game_home_main", {"ocr_results": []})

    assert result.success is True
    assert task._phase != InitAccountPhase.COMPLETED


def test_handle_page_should_complete_after_consecutive_home_hits_with_favorite_marker():
    """完成“喜欢卡牌”后，连续8次主页应触发兜底完成。"""

    task = InitAccountTask(adb=_DummyAdb(), recognizer=None, page_detector=object())
    task._mark_action_done("after_favorite_card")

    for _ in range(7):
        result = task.handle_page("game_home_main", {"ocr_results": []})
        assert result.success is True
        assert task._phase != InitAccountPhase.COMPLETED

    result = task.handle_page("game_home_main", {"ocr_results": []})
    assert result.success is True
    assert task._phase == InitAccountPhase.COMPLETED
