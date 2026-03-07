# -*- coding: utf-8 -*-
"""resources router 单元测试。"""

import asyncio

from starlette.requests import Request
from starlette.responses import HTMLResponse

from ptcgp_auto_v2.web.routers import resources as router


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


def test_get_management_resources_renders_template(monkeypatch):
    """资源管理页应渲染资源列表模板。"""
    _patch_render_template(monkeypatch)
    monkeypatch.setattr(
        router,
        "build_resources_context",
        lambda **_kwargs: {"items": [], "t": {}, "current_lang": "zh_CN"},
    )

    response = asyncio.run(
        router.get_management_resources(
            request=_build_request("GET"),
            view="stats",
            q="kw",
            sort_by="updated_at",
            sort_order="desc",
            page=0,
            page_size=10,
            session=object(),
        )
    )

    assert response.status_code == 200
    assert "tpl:partials/resource_list.html" in bytes(response.body).decode("utf-8")


def test_get_management_resources_passes_view_to_service(monkeypatch):
    """pack-points 视图应透传给服务层。"""
    _patch_render_template(monkeypatch)
    captured_kwargs = {}

    def _fake_build_resources_context(**kwargs):
        captured_kwargs.update(kwargs)
        return {"items": [], "t": {}, "current_lang": "zh_CN"}

    monkeypatch.setattr(
        router, "build_resources_context", _fake_build_resources_context
    )

    response = asyncio.run(
        router.get_management_resources(
            request=_build_request("GET"),
            view="pack-points",
            q="friend",
            sort_by="series:A1",
            sort_order="asc",
            page=1,
            page_size=5,
            session=object(),
        )
    )

    assert response.status_code == 200
    assert captured_kwargs["view"] == "pack-points"
    assert captured_kwargs["q"] == "friend"
    assert captured_kwargs["sort_by"] == "series:A1"
    assert captured_kwargs["sort_order"] == "asc"
    assert captured_kwargs["page"] == 1
    assert captured_kwargs["page_size"] == 5
