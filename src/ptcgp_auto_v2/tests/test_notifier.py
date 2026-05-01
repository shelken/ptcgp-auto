# -*- coding: utf-8 -*-
"""通知器回归测试。"""

from __future__ import annotations

from types import SimpleNamespace

from ptcgp_auto_v2.infra.notifier import Notifier


def test_notify_task_status_accepts_snapshot_without_account_relation(monkeypatch) -> None:
    """执行器传入纯快照时，通知器不能再读取 ORM account 关系。"""
    notifier = Notifier(webhook_url=None)
    captured: dict[str, object] = {}

    monkeypatch.setattr(
        notifier,
        "_load_scene_extra_config",
        lambda scene: (True, {"notify_on": ["failed"], "notify_task_types": []}),
    )

    def fake_notify(**kwargs):
        captured.update(kwargs)
        return True

    monkeypatch.setattr(notifier, "notify", fake_notify)

    task_snapshot = SimpleNamespace(
        id=7,
        account_id=3,
        task_type="send_card_daily",
    )
    account_snapshot = SimpleNamespace(
        id=3,
        nickname="skn306",
        display_name="skn306",
    )

    assert notifier.notify_task_status(
        task_snapshot,
        "failed",
        "连续 10 次停留在同一页面: profile_page",
        account=account_snapshot,
    ) is True

    assert captured["account_id"] == 3
    assert captured["task_instance_id"] == 7
    assert "skn306 (3)" in str(captured["content"])
    assert "send_card_daily" in str(captured["content"])
    assert "连续 10 次停留在同一页面: profile_page" in str(captured["content"])
