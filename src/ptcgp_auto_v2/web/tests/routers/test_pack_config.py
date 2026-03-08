# -*- coding: utf-8 -*-
"""pack_config router 单元测试。"""

import asyncio
from types import SimpleNamespace

from starlette.requests import Request
from starlette.responses import HTMLResponse

from ptcgp_auto_v2.web.routers import pack_config as router


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


def test_get_card_sets_returns_service_result(monkeypatch):
    """卡包系列接口应透传 service 返回。"""
    monkeypatch.setattr(router, "build_card_sets_options", lambda: [{"code": "A1"}])
    result = asyncio.run(router.get_card_sets())
    assert result == [{"code": "A1"}]


def test_get_boosters_options_renders_partial(monkeypatch):
    """补充包选项接口应返回 options partial。"""
    _patch_render_template(monkeypatch)
    monkeypatch.setattr(router, "build_set_boosters_options", lambda _set_code: ["Pikachu"])

    response = asyncio.run(
        router.get_boosters_options(
            request=_build_request("GET"),
            set_code="A1",
        )
    )
    assert response.status_code == 200
    assert "tpl:partials/options_boosters.html" in bytes(response.body).decode("utf-8")


def test_save_account_pack_config_returns_account_list_and_close_modal(monkeypatch):
    """保存配置后应刷新账号列表并触发 closeModal。"""
    _patch_render_template(monkeypatch)

    async def _fake_form():
        return SimpleNamespace(
            get=lambda key, default=None: {
                "set_code": "A1",
                "booster_name": "Pikachu",
            }.get(key, default)
        )

    request = _build_request("POST")
    request.form = _fake_form  # type: ignore[method-assign]

    called = {}

    def _fake_save_account_pack_config(account_id, set_code, booster_name):
        called["account_id"] = account_id
        called["set_code"] = set_code
        called["booster_name"] = booster_name

    monkeypatch.setattr(
        router, "build_save_account_pack_config", _fake_save_account_pack_config
    )
    monkeypatch.setattr(
        router,
        "build_accounts_list_context",
        lambda **_kwargs: {
            "items": [],
            "pack_configs": {},
            "auto_pack_map": {},
            "q": "",
            "sort_by": "id",
            "sort_order": "asc",
            "page": 0,
            "page_size": 10,
            "has_prev": False,
            "has_next": False,
            "total": 0,
        },
    )

    response = asyncio.run(
        router.save_account_pack_config_api(
            request=request,
            account_id=3,
            session=object(),
        )
    )

    assert response.status_code == 200
    assert called == {"account_id": 3, "set_code": "A1", "booster_name": "Pikachu"}
    assert response.headers.get("HX-Trigger") == "closeModal"
