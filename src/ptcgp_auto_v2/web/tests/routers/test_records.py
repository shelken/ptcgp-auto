# -*- coding: utf-8 -*-
"""records router 单元测试。"""

import asyncio
from typing import cast

from starlette.requests import Request
from starlette.responses import HTMLResponse

from ptcgp_auto_v2.web.routers import records as router


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


def test_get_records_renders_record_list(monkeypatch):
    """记录列表接口应返回 record_list 模板。"""
    _patch_templates(monkeypatch)
    monkeypatch.setattr(
        router,
        "list_records",
        lambda *args, **kwargs: {"records": [], "t": {}, "current_lang": "zh_CN"},
    )

    response = asyncio.run(
        router.get_records(
            request=_build_request("GET"),
            page=0,
            page_size=10,
            rarity=[],
            card_type=[],
            lang="zh_CN",
            session=object(),
        )
    )
    html_response = cast(HTMLResponse, response)
    assert html_response.status_code == 200
    assert "tpl:partials/record_list.html" in bytes(html_response.body).decode("utf-8")


def test_get_records_returns_empty_when_stop(monkeypatch):
    """记录列表 stop=True 时应返回空串。"""
    monkeypatch.setattr(router, "list_records", lambda *args, **kwargs: {"stop": True})

    response = asyncio.run(
        router.get_records(
            request=_build_request("GET"),
            page=1,
            page_size=10,
            rarity=[],
            card_type=[],
            lang="zh_CN",
            session=object(),
        )
    )
    assert response == ""
