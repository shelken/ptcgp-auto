# -*- coding: utf-8 -*-
"""friendship router 单元测试。"""

import asyncio
import json
from types import SimpleNamespace
from urllib.parse import urlencode

from starlette.requests import Request
from starlette.responses import HTMLResponse

from ptcgp_auto_v2.web.routers import friendship as router


def _build_request(method: str = "GET", query: dict | None = None) -> Request:
    """构建最小 Request 对象。"""
    scope = {
        "type": "http",
        "method": method,
        "path": "/",
        "query_string": urlencode(query or {}).encode("utf-8"),
        "headers": [],
        "cookies": {},
    }

    async def receive():
        return {"type": "http.request", "body": b"", "more_body": False}

    return Request(scope, receive)


def _patch_templates(monkeypatch):
    """替换模板引擎，避免依赖真实模板渲染。"""

    class _FakeTemplates:
        def TemplateResponse(self, name, context):
            return HTMLResponse(
                content=f"tpl:{name};keys:{','.join(sorted(context.keys()))}"
            )

    monkeypatch.setattr(router, "get_templates", lambda: _FakeTemplates())


class _FakeSession:
    """最小 Session 替身。"""

    def __init__(self, account=None):
        self._account = account

    def get(self, _model, _pk):
        return self._account


def test_get_management_friendships_renders_template(monkeypatch):
    """好友管理页应渲染 friendship 列表模板。"""
    _patch_templates(monkeypatch)
    request = _build_request("GET")

    def _fake_build_friendship_context(
        session,
        lang,
        account_id,
        from_account_id,
        q,
        sort_by,
        sort_order,
        page,
        page_size,
    ):
        assert account_id == 12
        assert from_account_id == 34
        assert q == "abc"
        assert sort_by == "created_at"
        assert sort_order == "desc"
        assert page == 0
        assert page_size == 10
        return {"items": [], "t": {}, "current_lang": lang}

    monkeypatch.setattr(
        router, "build_friendship_context", _fake_build_friendship_context
    )

    response = asyncio.run(
        router.get_management_friendships(
            request=request,
            lang="zh_CN",
            account_id="12",
            from_account_id="34",
            q="abc",
            sort_by="created_at",
            sort_order="desc",
            page=0,
            page_size=10,
            session=_FakeSession(),
        )
    )

    assert response.status_code == 200
    assert "tpl:partials/friendship_list.html" in bytes(response.body).decode("utf-8")


def test_post_add_friend_request_passes_filters_and_sets_success_toast(monkeypatch):
    """添加好友成功后应透传筛选参数并返回成功提示。"""
    request = _build_request("POST")

    async def _fake_form():
        return SimpleNamespace(
            get=lambda key, default=None: {
                "from_account_id": "1",
                "to_account_id": "2",
                "to_friend_id": "",
                "selected_account_id": "7",
                "selected_from_account_id": "8",
                "q": "kw",
                "sort_by": "created_at",
                "sort_order": "desc",
                "page": "2",
                "page_size": "20",
            }.get(key, default)
        )

    request.form = _fake_form  # type: ignore[method-assign]

    called = {}

    async def _fake_get_management_friendships(
        request,
        lang,
        account_id,
        from_account_id,
        q,
        sort_by,
        sort_order,
        page,
        page_size,
        session,
    ):
        called["account_id"] = account_id
        called["from_account_id"] = from_account_id
        called["q"] = q
        called["sort_by"] = sort_by
        called["sort_order"] = sort_order
        called["page"] = page
        called["page_size"] = page_size
        return HTMLResponse("ok")

    monkeypatch.setattr(
        router, "get_management_friendships", _fake_get_management_friendships
    )
    monkeypatch.setattr(router, "create_add_request", lambda **_kwargs: True)
    monkeypatch.setattr(
        router,
        "build_friendship_context",
        lambda session, lang: {
            "t": {"msg_add_request_created": "添加成功"},
            "current_lang": lang,
        },
    )

    fake_account = SimpleNamespace(friend_id="F123")
    response = asyncio.run(
        router.post_add_friend_request(
            request=request,
            lang="zh_CN",
            session=_FakeSession(account=fake_account),
        )
    )

    assert response.status_code == 200
    assert called == {
        "account_id": "7",
        "from_account_id": "8",
        "q": "kw",
        "sort_by": "created_at",
        "sort_order": "desc",
        "page": 2,
        "page_size": 20,
    }
    trigger = json.loads(response.headers["HX-Trigger"])
    assert trigger["showToast"]["message"] == "添加成功"


def test_post_delete_friend_request_failure_sets_skip_toast(monkeypatch):
    """删除好友失败时应返回失败提示。"""
    request = _build_request("POST")

    async def _fake_form():
        return SimpleNamespace(
            get=lambda key, default=None: {
                "from_account_id": "1",
                "to_account_id": "2",
                "friend_id": "",
                "selected_account_id": "9",
                "selected_from_account_id": "10",
                "q": "d",
                "sort_by": "created_at",
                "sort_order": "desc",
                "page": "0",
                "page_size": "10",
            }.get(key, default)
        )

    request.form = _fake_form  # type: ignore[method-assign]

    async def _fake_get_management_friendships(**_kwargs):
        return HTMLResponse("ok")

    monkeypatch.setattr(
        router, "get_management_friendships", _fake_get_management_friendships
    )
    monkeypatch.setattr(router, "create_delete_request", lambda **_kwargs: False)
    monkeypatch.setattr(
        router,
        "build_friendship_context",
        lambda session, lang: {
            "t": {"msg_delete_request_skipped_not_friend": "不是好友"},
            "current_lang": lang,
        },
    )

    fake_account = SimpleNamespace(friend_id="F456")
    response = asyncio.run(
        router.post_delete_friend_request(
            request=request,
            lang="zh_CN",
            session=_FakeSession(account=fake_account),
        )
    )

    assert response.status_code == 200
    trigger = json.loads(response.headers["HX-Trigger"])
    assert trigger["showToast"]["message"] == "不是好友"


def test_post_cancel_friend_request_sets_success_toast(monkeypatch):
    """取消请求成功时应返回成功提示。"""

    async def _fake_get_management_friendships(**_kwargs):
        return HTMLResponse("ok")

    monkeypatch.setattr(
        router, "get_management_friendships", _fake_get_management_friendships
    )
    monkeypatch.setattr(router, "cancel_pending_request", lambda request_id: True)
    monkeypatch.setattr(
        router,
        "build_friendship_context",
        lambda session, lang: {
            "t": {"msg_request_cancelled": "取消成功"},
            "current_lang": lang,
        },
    )

    response = asyncio.run(
        router.post_cancel_friend_request(
            request_id=101,
            request=_build_request("POST"),
            lang="zh_CN",
            selected_account_id="7",
            selected_from_account_id="8",
            q="kw",
            sort_by="created_at",
            sort_order="desc",
            page=1,
            page_size=10,
            session=_FakeSession(),
        )
    )

    assert response.status_code == 200
    trigger = json.loads(response.headers["HX-Trigger"])
    assert trigger["showToast"]["message"] == "取消成功"
