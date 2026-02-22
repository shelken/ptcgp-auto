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


def _patch_templates(monkeypatch):
    """替换模板引擎，避免依赖真实模板渲染。"""

    class _FakeTemplates:
        def TemplateResponse(self, name, context):
            return HTMLResponse(
                content=f"tpl:{name};keys:{','.join(sorted(context.keys()))}"
            )

    monkeypatch.setattr(router, "get_templates", lambda: _FakeTemplates())


def test_save_plan_refresh_passes_plain_query_values(monkeypatch):
    """保存计划后刷新列表时，传给服务层的查询参数应是原生类型。"""
    _patch_templates(monkeypatch)

    async def _fake_form():
        return SimpleNamespace()

    request = _build_request("POST")
    request.form = _fake_form  # type: ignore[method-assign]

    monkeypatch.setattr(router, "upsert_plan_from_form", lambda form: None)

    def _fake_get_plans_context(
        lang: str,
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
            "plans": [],
            "q": q,
            "sort_by": sort_by,
            "sort_order": sort_order,
            "page": page,
            "page_size": page_size,
            "has_prev": False,
            "has_next": False,
            "total_items": 0,
            "t": {},
            "current_lang": "zh_CN",
        }

    monkeypatch.setattr(router, "get_plans_context", _fake_get_plans_context)

    response = asyncio.run(router.save_plan(request=request, lang="zh_CN"))
    assert response.status_code == 200
    assert response.headers.get("HX-Trigger") == "closeModal"
