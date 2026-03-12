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


def _patch_render_template(monkeypatch):
    """替换 render_template，避免依赖真实模板渲染。"""

    monkeypatch.setattr(
        router,
        "render_template",
        lambda _request, template, context: HTMLResponse(
            content=f"tpl:{template};keys:{','.join(sorted(context.keys()))}"
        ),
    )


def test_get_management_daily_gift_renders_with_query_protocol(monkeypatch):
    """daily-gift 管理页应支持 biz_date_local/q/sort/page 参数渲染。"""
    _patch_render_template(monkeypatch)

    captured = {}

    def _fake_build_daily_gift_context(**kwargs):
        captured.update(
            {
                "biz_date_local": kwargs["biz_date_local"],
                "account_id": kwargs["account_id"],
                "q": kwargs["q"],
                "sort_by": kwargs["sort_by"],
                "sort_order": kwargs["sort_order"],
                "page": kwargs["page"],
                "page_size": kwargs["page_size"],
                "pair_page": kwargs["pair_page"],
                "pair_page_size": kwargs["pair_page_size"],
            }
        )
        return {"records": [], "t": {}, "current_lang": "zh_CN"}

    monkeypatch.setattr(
        router, "build_daily_gift_context", _fake_build_daily_gift_context
    )

    response = asyncio.run(
        router.get_management_daily_gift(
            request=_build_request("GET"),
            biz_date_local="2026-02-22",
            account_id="7",
            q="abc",
            sort_by="updated_at",
            sort_order="desc",
            page=2,
            page_size=20,
            pair_page=3,
            pair_page_size=15,
            session=object(),
        )
    )

    assert response.status_code == 200
    assert "tpl:partials/daily_gift_list.html" in bytes(response.body).decode("utf-8")
    assert captured == {
        "biz_date_local": "2026-02-22",
        "account_id": 7,
        "q": "abc",
        "sort_by": "updated_at",
        "sort_order": "desc",
        "page": 2,
        "page_size": 20,
        "pair_page": 3,
        "pair_page_size": 15,
    }
