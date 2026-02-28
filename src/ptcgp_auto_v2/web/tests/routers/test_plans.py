# -*- coding: utf-8 -*-
"""plans router 回归测试。"""

import asyncio
from types import SimpleNamespace

from starlette.requests import Request
from starlette.responses import HTMLResponse

from ptcgp_auto_v2.web.routers import plans as router


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


def test_save_plan_refresh_passes_plain_query_values(monkeypatch):
    """保存计划后刷新列表时，传给服务层的查询参数应是原生类型。"""
    _patch_render_template(monkeypatch)

    async def _fake_form():
        return SimpleNamespace()

    request = _build_request("POST")
    request.form = _fake_form  # type: ignore[method-assign]

    monkeypatch.setattr(router, "upsert_plan_from_form", lambda form: None)

    def _fake_build_plans_list_context(
        *,
        session,
        q: str = "",
        sort_by: str = "id",
        sort_order: str = "asc",
        page: int = 0,
        page_size: int = 10,
    ):
        assert isinstance(q, str)
        assert isinstance(sort_by, str)
        assert isinstance(sort_order, str)
        assert isinstance(page, int)
        assert isinstance(page_size, int)
        return {
            "items": [],
            "q": q,
            "sort_by": sort_by,
            "sort_order": sort_order,
            "page": page,
            "page_size": page_size,
            "has_prev": False,
            "has_next": False,
            "total": 0,
        }

    monkeypatch.setattr(
        router, "build_plans_list_context", _fake_build_plans_list_context
    )

    response = asyncio.run(router.save_plan(request=request, session=object()))
    assert response.status_code == 200
    assert response.headers.get("HX-Trigger") == "closeModal"
