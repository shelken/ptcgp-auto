# -*- coding: utf-8 -*-
"""task_service 回归测试。"""

from datetime import datetime
from types import SimpleNamespace

from ptcgp_auto_v2.web.services import task_service


def test_build_tasks_list_context_does_not_compute_auto_pack_inline(monkeypatch):
    """任务列表首屏不应同步计算 open_pack 自动目标包。"""

    fake_instance = SimpleNamespace(
        id=1,
        account_id=10,
        account=SimpleNamespace(id=10, nickname="Alpha", display_name="Alpha"),
        task_type="open_pack",
        status="pending",
        last_completed_at=None,
        last_duration_seconds=None,
        updated_at=datetime.now(),
        error_message=None,
        next_run_at=None,
    )

    monkeypatch.setattr(
        task_service,
        "fetch_task_instances",
        lambda **_kwargs: ([fake_instance], False, 1),
    )
    monkeypatch.setattr(
        task_service,
        "select_pack_for_account",
        lambda **_kwargs: (_ for _ in ()).throw(
            AssertionError("不应同步计算自动目标包")
        ),
    )
    monkeypatch.setattr(
        task_service, "build_account_plan_cache", lambda _account: {"config": {}}
    )
    monkeypatch.setattr(
        task_service,
        "compute_next_run_for_instance",
        lambda _instance, _cache: (None, SimpleNamespace(value="daily"), None, None),
    )

    class _FakeExecResult:
        def all(self):
            return []

    class _FakeSession:
        def exec(self, _statement):
            return _FakeExecResult()

    context = task_service.build_tasks_list_context(
        session=_FakeSession(),
        page=0,
        page_size=10,
        status=[],
        task_type=[],
        account_id=None,
        sort_by="dispatch_priority",
        sort_order="asc",
    )

    assert len(context["items"]) == 1
    assert context["items"][0]["target_pack_label"] is None
    assert context["items"][0]["target_pack_auto"] is False


def test_list_task_filter_accounts_uses_lightweight_search_query(monkeypatch):
    """任务筛选账号列表不应再走全量仓储 get_all。"""

    monkeypatch.setattr(
        task_service,
        "AccountRepository",
        lambda: SimpleNamespace(
            get_all=lambda: (_ for _ in ()).throw(AssertionError("不应再调用 get_all"))
        ),
    )

    class _FakeExecResult:
        def all(self):
            return [SimpleNamespace(id=1, nickname="Alpha", display_name="Alpha")]

    class _FakeSession:
        def exec(self, _statement):
            return _FakeExecResult()

    items = task_service.list_task_filter_accounts(
        session=_FakeSession(), q="alp", limit=20
    )
    assert len(items) == 1
    assert items[0].id == 1
