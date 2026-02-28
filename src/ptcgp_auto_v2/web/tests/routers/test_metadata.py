# -*- coding: utf-8 -*-
"""metadata router 单元测试。"""

import asyncio

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


def _patch_render_template(monkeypatch):
    """替换 render_template，避免依赖真实模板渲染。"""

    monkeypatch.setattr(
        router,
        "render_template",
        lambda _request, template, context: HTMLResponse(
            content=f"tpl:{template};keys:{','.join(sorted(context.keys()))}"
        ),
    )


def test_get_management_metadata_renders_template(monkeypatch):
    """元数据管理页应渲染列表模板。"""
    _patch_render_template(monkeypatch)
    monkeypatch.setattr(
        router,
        "build_metadata_context",
        lambda **_kwargs: {
            "rows": [],
            "t": {},
            "current_lang": "zh_CN",
            "sets": [],
            "packs_by_set": {},
            "sync_check": {},
            "selected_node_type": "root",
            "selected_node_id": "all",
            "selected_set_code": "",
            "selected_pack_name": "",
            "selected_card_key": "",
            "selected_pack_cards": [],
            "ui_step": _kwargs.get("ui_step", 1),
        },
    )

    response = asyncio.run(
        router.get_management_metadata(
            request=_build_request("GET"),
        )
    )
    assert response.status_code == 200
    assert "tpl:partials/metadata_list.html" in bytes(response.body).decode("utf-8")
