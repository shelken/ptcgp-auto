# -*- coding: utf-8 -*-
"""index router 单元测试。"""

import asyncio

from starlette.requests import Request
from starlette.responses import HTMLResponse

from ptcgp_auto_v2.web.routers import index as router


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


def test_read_root_renders_index_template(monkeypatch):
    """首页接口应返回 index 模板。"""
    _patch_templates(monkeypatch)
    monkeypatch.setattr(
        router,
        "build_index_context",
        lambda _session, _lang: {"t": {}, "current_lang": "zh_CN"},
    )

    response = asyncio.run(
        router.read_root(
            request=_build_request("GET"),
            lang="zh_CN",
            session=object(),
        )
    )

    assert response.status_code == 200
    assert "tpl:index.html" in bytes(response.body).decode("utf-8")
