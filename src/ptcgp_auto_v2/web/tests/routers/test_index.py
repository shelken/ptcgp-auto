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


def _patch_render_template(monkeypatch):
    """替换 render_template，避免依赖真实模板渲染。"""

    monkeypatch.setattr(
        router,
        "render_template",
        lambda _request, template, context: HTMLResponse(
            content=f"tpl:{template};keys:{','.join(sorted(context.keys()))}"
        ),
    )


def test_read_root_renders_index_template(monkeypatch):
    """首页接口应返回 index 模板。"""
    _patch_render_template(monkeypatch)
    monkeypatch.setattr(
        router,
        "build_index_context",
        lambda _session: {"t": {}, "current_lang": "zh_CN"},
    )

    response = asyncio.run(
        router.read_root(
            request=_build_request("GET"),
            session=object(),
        )
    )

    assert response.status_code == 200
    assert "tpl:index.html" in bytes(response.body).decode("utf-8")


def test_index_module_uses_index_template_path() -> None:
    """首页路由模块应继续使用 index 模板。"""
    import inspect

    source = inspect.getsource(router.read_root)

    assert '"index.html"' in source or "'index.html'" in source
