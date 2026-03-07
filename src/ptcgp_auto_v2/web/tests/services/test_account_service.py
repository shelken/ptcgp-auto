# -*- coding: utf-8 -*-
"""account_service 回归测试。"""

from types import SimpleNamespace

from ptcgp_auto_v2.web.services import account_service


def test_build_accounts_list_context_does_not_compute_auto_pack_inline(monkeypatch):
    """账号列表首屏不应同步计算自动目标包。"""

    fake_accounts = [
        SimpleNamespace(
            id=1,
            nickname="Alpha",
            display_name="Alpha",
            friend_id="1234567890123456",
            game_id="game-alpha",
            task_plan_associations=[],
        )
    ]

    class _FakeRepo:
        def get_all(self):
            return fake_accounts

    monkeypatch.setattr(account_service, "AccountRepository", lambda: _FakeRepo())
    monkeypatch.setattr(
        account_service,
        "select_pack_for_account",
        lambda **_kwargs: (_ for _ in ()).throw(
            AssertionError("不应同步计算自动目标包")
        ),
    )

    class _FakeConfig:
        account_id = 999

    class _FakeExecResult:
        def all(self):
            return [_FakeConfig()]

    class _FakeSession:
        def exec(self, _statement):
            return _FakeExecResult()

    context = account_service.build_accounts_list_context(
        session=_FakeSession(),
        q="",
        sort_by="id",
        sort_order="asc",
        page=0,
        page_size=10,
    )

    assert context["items"] == fake_accounts
    assert context["auto_pack_map"] == {}
    assert 1 not in context["pack_configs"]
