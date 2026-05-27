# -*- coding: utf-8 -*-
"""每日送卡「好友列表为空」跳过 + 删除假好友回归测试。"""

from types import SimpleNamespace
from unittest.mock import MagicMock

import ptcgp_auto_v2.tasks.send_card_daily as send_card_daily_module
from ptcgp_auto_v2.core.task_state import TaskState
from ptcgp_auto_v2.tasks.send_card_daily import SendCardDailyTask


class _Adb:
    pass


class _Account:
    def __init__(self, account_id: int | None):
        self.id = account_id


def _task(monkeypatch):
    monkeypatch.setattr(
        send_card_daily_module,
        "get_settings",
        lambda: SimpleNamespace(app_package="game.package"),
        raising=False,
    )
    monkeypatch.setattr(
        send_card_daily_module,
        "session_scope",
        MagicMock(),
        raising=False,
    )

    task = SendCardDailyTask.__new__(SendCardDailyTask)
    task.adb = _Adb()
    task.state = TaskState()
    task.bind_account(_Account(account_id=123))
    task.card_recognizer = MagicMock()
    return task


def _prepare_mocks(monkeypatch, task, target_friend_id: str | None = "friend_98765"):
    """准备公共 mock 并返回 fake_friendship_repo。"""
    task.state_set("target_friend_id", target_friend_id)
    task.state_set("record_id", 42)

    monkeypatch.setattr(
        send_card_daily_module,
        "is_text_visible",
        lambda *args, **kwargs: True,
        raising=False,
    )
    monkeypatch.setattr(
        send_card_daily_module,
        "get_text_patterns",
        lambda key: [f"mock_{key}"],
        raising=False,
    )

    fake_friendship_repo = MagicMock()
    monkeypatch.setattr(
        send_card_daily_module,
        "FriendshipRepository",
        lambda session: fake_friendship_repo,
        raising=False,
    )

    fake_helper = MagicMock()
    task.state_set("friend_helper", fake_helper)

    monkeypatch.setattr(
        send_card_daily_module,
        "GiftRecordService",
        MagicMock(),
        raising=False,
    )

    fake_flow = MagicMock()
    task.state_set("friend_flow", fake_flow)

    return fake_friendship_repo


def test_delete_friendship_when_friend_list_empty(monkeypatch):
    """好友选择页 OCR 显示"沒有朋友"时删除好友关系并跳过。"""
    task = _task(monkeypatch)
    fake_repo = _prepare_mocks(monkeypatch, task, "friend_98765")

    page_info = {"ocr_results": [("沒有朋友。", (300, 600))]}
    result = task._handle_choose_friend(page_info)

    assert result is not None
    assert result.success is True
    fake_repo.delete.assert_called_once_with(123, "friend_98765")


def test_skip_when_friend_list_empty_keeps_friendship_if_no_account_id(monkeypatch):
    """account.id 为空时不删好友关系，但跳过。"""
    task = _task(monkeypatch)
    task.bind_account(_Account(account_id=None))
    fake_repo = _prepare_mocks(monkeypatch, task, "friend_98765")

    page_info = {"ocr_results": [("沒有朋友。", (300, 600))]}
    result = task._handle_choose_friend(page_info)

    assert result is not None
    assert result.success is True
    fake_repo.delete.assert_not_called()


def test_skip_when_friend_list_empty_keeps_friendship_if_no_target_id(monkeypatch):
    """target_friend_id 为空时不删好友关系，但跳过。"""
    task = _task(monkeypatch)
    fake_repo = _prepare_mocks(monkeypatch, task, None)

    page_info = {"ocr_results": [("沒有朋友。", (300, 600))]}
    result = task._handle_choose_friend(page_info)

    assert result is not None
    assert result.success is True
    fake_repo.delete.assert_not_called()
