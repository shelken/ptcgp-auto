# -*- coding: utf-8 -*-
"""metadata router 单元测试。"""

import asyncio
from types import SimpleNamespace

from starlette.requests import Request
from starlette.responses import HTMLResponse

from ptcgp_auto_v2.web.routers import metadata as router


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


def test_get_management_metadata_renders_template(monkeypatch):
    """元数据管理页应渲染列表模板。"""
    _patch_templates(monkeypatch)
    monkeypatch.setattr(
        router,
        "build_metadata_context",
        lambda _lang: {"rows": [], "t": {}, "current_lang": "zh_CN"},
    )

    response = asyncio.run(
        router.get_management_metadata(
            request=_build_request("GET"),
            lang="zh_CN",
        )
    )
    assert response.status_code == 200
    assert "tpl:partials/metadata_list.html" in bytes(response.body).decode("utf-8")


def test_update_set_label_refreshes_management_partial(monkeypatch):
    """更新系列名后应返回管理页片段。"""
    _patch_templates(monkeypatch)

    async def _fake_form():
        return SimpleNamespace(
            get=lambda key, default=None: {"label_zh": "系列A"}.get(key, default)
        )

    request = _build_request("POST")
    request.form = _fake_form  # type: ignore[method-assign]

    called = {}
    monkeypatch.setattr(
        router,
        "build_metadata_context",
        lambda _lang: {"rows": [], "t": {}, "current_lang": "zh_CN"},
    )
    monkeypatch.setattr(
        router,
        "update_set_label",
        lambda code, label_zh: called.update({"code": code, "label_zh": label_zh}),
    )

    response = asyncio.run(
        router.update_set_label_api(request=request, code="A1", lang="zh_CN")
    )
    assert response.status_code == 200
    assert called == {"code": "A1", "label_zh": "系列A"}


def test_update_pack_label_refreshes_management_partial(monkeypatch):
    """更新补充包名后应返回管理页片段。"""
    _patch_templates(monkeypatch)

    async def _fake_form():
        return SimpleNamespace(
            get=lambda key, default=None: {"label_zh": "补充包A"}.get(key, default)
        )

    request = _build_request("POST")
    request.form = _fake_form  # type: ignore[method-assign]

    called = {}
    monkeypatch.setattr(
        router,
        "build_metadata_context",
        lambda _lang: {"rows": [], "t": {}, "current_lang": "zh_CN"},
    )
    monkeypatch.setattr(
        router,
        "update_pack_label",
        lambda name, label_zh: called.update({"name": name, "label_zh": label_zh}),
    )

    response = asyncio.run(
        router.update_pack_label_api(request=request, name="p1", lang="zh_CN")
    )
    assert response.status_code == 200
    assert called == {"name": "p1", "label_zh": "补充包A"}
