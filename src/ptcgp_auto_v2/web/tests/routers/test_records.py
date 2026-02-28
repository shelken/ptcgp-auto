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


def test_get_records_renders_record_list(monkeypatch):
    """记录列表接口应返回 record_list 模板。"""
    monkeypatch.setattr(
        router,
        "build_records_list_context",
        lambda *args, **kwargs: {"items": [], "page": 0, "has_prev": False, "has_next": False},
    )

    monkeypatch.setattr(
        router,
        "render_template",
        lambda _request, template, _context: HTMLResponse(content=f"tpl:{template}"),
    )

    response = asyncio.run(
        router.get_records(
            request=_build_request("GET"),
            page=0,
            page_size=10,
            rarity=[],
            card_type=[],
            session=object(),
        )
    )
    html_response = cast(HTMLResponse, response)
    assert html_response.status_code == 200
    assert "tpl:partials/record_list.html" in bytes(html_response.body).decode("utf-8")
