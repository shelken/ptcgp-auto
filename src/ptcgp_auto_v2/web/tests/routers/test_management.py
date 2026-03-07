# -*- coding: utf-8 -*-
"""management router 回归测试。"""

import asyncio
from types import SimpleNamespace

from starlette.requests import Request
from starlette.responses import HTMLResponse

from ptcgp_auto_v2.web.routers import management as router


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


def test_update_account_details_refresh_passes_plain_query_values(monkeypatch):
    """保存账号信息后刷新列表时，传给服务层的查询参数应是原生类型。"""
    _patch_render_template(monkeypatch)

    async def _fake_form():
        return SimpleNamespace(get=lambda _key, default=None: default)

    request = _build_request("POST")
    request.form = _fake_form  # type: ignore[method-assign]

    monkeypatch.setattr(
        router, "update_account_details", lambda *_args, **_kwargs: None
    )

    def _fake_build_accounts_list_context(
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
            "pack_configs": {},
            "auto_pack_map": {},
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
        router, "build_accounts_list_context", _fake_build_accounts_list_context
    )

    response = asyncio.run(
        router.update_account_details_api(
            request=request,
            account_id=1,
            session=object(),
        )
    )
    assert response.status_code == 200
    assert response.headers.get("HX-Trigger") == "closeModal"


def test_get_account_target_pack_cell_uses_dedicated_partial(monkeypatch):
    """账号目标包单元格应通过独立路由渲染。"""
    _patch_render_template(monkeypatch)

    captured = {}

    def _fake_build_account_target_pack_context(account_id: int):
        captured["account_id"] = account_id
        return {
            "account_id": account_id,
            "config": None,
            "auto_pack": {"pack_code": "A1", "booster_name": "Pikachu"},
        }

    monkeypatch.setattr(
        router,
        "build_account_target_pack_context",
        _fake_build_account_target_pack_context,
    )

    response = asyncio.run(
        router.get_account_target_pack_cell(
            request=_build_request("GET"),
            account_id=7,
        )
    )

    assert captured == {"account_id": 7}
    assert response.status_code == 200
    assert "tpl:partials/account_target_pack_cell.html" in bytes(response.body).decode(
        "utf-8"
    )
