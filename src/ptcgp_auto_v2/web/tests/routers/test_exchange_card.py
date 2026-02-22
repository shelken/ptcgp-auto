# -*- coding: utf-8 -*-
"""exchange_card router 单元测试。"""

import asyncio
import json

from starlette.requests import Request
from starlette.responses import HTMLResponse

from ptcgp_auto_v2.web.routers import exchange_card as router


def _build_request(method: str = "GET") -> Request:
    """构建最小 Request 对象。"""
    scope = {
        "type": "http",
        "method": method,
        "path": "/",
        "query_string": b"",
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


def test_get_management_exchange_cards_renders_template(monkeypatch):
    """交换记录管理页应渲染列表模板。"""
    _patch_templates(monkeypatch)
    monkeypatch.setattr(
        router,
        "build_exchange_card_context",
        lambda **_kwargs: {"items": [], "t": {}, "current_lang": "zh_CN"},
    )

    response = asyncio.run(
        router.get_management_exchange_cards(
            request=_build_request("GET"),
            lang="zh_CN",
            account_id="1",
            status="pending",
            q="kw",
            sort_by="created_at",
            sort_order="desc",
            page=0,
            page_size=10,
            session=object(),
        )
    )
    assert response.status_code == 200
    assert "tpl:partials/exchange_card_list.html" in bytes(response.body).decode(
        "utf-8"
    )


def test_post_cancel_exchange_request_success_sets_success_toast(monkeypatch):
    """取消请求成功时应返回成功提示。"""

    async def _fake_get_management_exchange_cards(**_kwargs):
        return HTMLResponse("ok")

    monkeypatch.setattr(
        router,
        "get_management_exchange_cards",
        _fake_get_management_exchange_cards,
    )
    monkeypatch.setattr(router, "cancel_exchange_request", lambda **_kwargs: True)
    monkeypatch.setattr(
        router,
        "build_exchange_card_context",
        lambda **_kwargs: {"t": {"msg_exchange_request_cancelled": "取消成功"}},
    )

    response = asyncio.run(
        router.post_cancel_exchange_request(
            request_id=1,
            request=_build_request("POST"),
            lang="zh_CN",
            account_id="1",
            status="pending",
            q="kw",
            sort_by="created_at",
            sort_order="desc",
            page=0,
            page_size=10,
            session=object(),
        )
    )
    assert response.status_code == 200
    trigger = json.loads(response.headers["HX-Trigger"])
    assert trigger["showToast"]["message"] == "取消成功"


def test_post_cancel_exchange_request_failure_sets_failed_toast(monkeypatch):
    """取消请求失败时应返回失败提示。"""

    async def _fake_get_management_exchange_cards(**_kwargs):
        return HTMLResponse("ok")

    monkeypatch.setattr(
        router,
        "get_management_exchange_cards",
        _fake_get_management_exchange_cards,
    )
    monkeypatch.setattr(router, "cancel_exchange_request", lambda **_kwargs: False)
    monkeypatch.setattr(
        router,
        "build_exchange_card_context",
        lambda **_kwargs: {"t": {"msg_exchange_request_cancel_failed": "取消失败"}},
    )

    response = asyncio.run(
        router.post_cancel_exchange_request(
            request_id=2,
            request=_build_request("POST"),
            lang="zh_CN",
            account_id="1",
            status="pending",
            q="kw",
            sort_by="created_at",
            sort_order="desc",
            page=1,
            page_size=10,
            session=object(),
        )
    )
    assert response.status_code == 200
    trigger = json.loads(response.headers["HX-Trigger"])
    assert trigger["showToast"]["message"] == "取消失败"
