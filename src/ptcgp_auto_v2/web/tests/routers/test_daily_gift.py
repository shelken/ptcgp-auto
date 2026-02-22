# -*- coding: utf-8 -*-
"""daily_gift router 单元测试。"""

import asyncio

from starlette.requests import Request
from starlette.responses import HTMLResponse

from ptcgp_auto_v2.web.routers import daily_gift as router


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


def test_get_management_daily_gift_renders_with_query_protocol(monkeypatch):
    """daily-gift 管理页应支持 biz_date_local/q/sort/page 参数渲染。"""
    _patch_templates(monkeypatch)

    captured = {}

    def _fake_build_daily_gift_context(**kwargs):
        captured.update(
            {
                "biz_date_local": kwargs["biz_date_local"],
                "q": kwargs["q"],
                "sort_by": kwargs["sort_by"],
                "sort_order": kwargs["sort_order"],
                "page": kwargs["page"],
                "page_size": kwargs["page_size"],
            }
        )
        return {"records": [], "t": {}, "current_lang": kwargs["lang"]}

    monkeypatch.setattr(
        router, "build_daily_gift_context", _fake_build_daily_gift_context
    )

    response = asyncio.run(
        router.get_management_daily_gift(
            request=_build_request("GET"),
            lang="zh_CN",
            biz_date_local="2026-02-22",
            q="abc",
            sort_by="updated_at",
            sort_order="desc",
            page=2,
            page_size=20,
            session=object(),
        )
    )

    assert response.status_code == 200
    assert "tpl:partials/daily_gift_list.html" in bytes(response.body).decode("utf-8")
    assert captured == {
        "biz_date_local": "2026-02-22",
        "q": "abc",
        "sort_by": "updated_at",
        "sort_order": "desc",
        "page": 2,
        "page_size": 20,
    }
