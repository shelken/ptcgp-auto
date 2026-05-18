# -*- coding: utf-8 -*-
"""每日送卡卡死恢复测试。"""

from types import SimpleNamespace

import ptcgp_auto_v2.tasks.send_card_daily as send_card_daily_module
from ptcgp_auto_v2.tasks.send_card_daily import SendCardDailyTask


class _Adb:
    def __init__(self):
        self.restarted_packages: list[str] = []

    def restart_app(self, package_name: str):
        self.restarted_packages.append(package_name)


def _task(monkeypatch):
    task = SendCardDailyTask.__new__(SendCardDailyTask)
    task.adb = _Adb()
    task.on_start_calls = 0
    task.on_start = lambda: setattr(task, "on_start_calls", task.on_start_calls + 1)
    monkeypatch.setattr(
        send_card_daily_module,
        "get_settings",
        lambda: SimpleNamespace(app_package="game.package"),
        raising=False,
    )
    return task


def test_send_card_daily_restarts_once_for_known_stuck_page(monkeypatch):
    """已知送卡卡死页面首次停滞时重启 App，并继续当前任务。"""
    task = _task(monkeypatch)

    result = task.handle_same_page_stuck("gift_select_card", {}, 10)
    second_result = task.handle_same_page_stuck("gift_select_card", {}, 10)

    assert result is not None
    assert result.success is True
    assert result.should_wait == 8.0
    assert second_result is None
    assert task.adb.restarted_packages == ["game.package"]
    assert task.on_start_calls == 1


def test_send_card_daily_does_not_restart_unknown_stuck_page(monkeypatch):
    """非送卡已知卡死页面保持原同页失败逻辑。"""
    task = _task(monkeypatch)

    result = task.handle_same_page_stuck("profile_page", {}, 10)

    assert result is None
    assert task.adb.restarted_packages == []
    assert task.on_start_calls == 0
