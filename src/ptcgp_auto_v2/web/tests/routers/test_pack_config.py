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


def _patch_templates(monkeypatch):
    """替换模板引擎，避免依赖真实模板渲染。"""

    class _FakeTemplates:
        def TemplateResponse(self, name, context):
            return HTMLResponse(
                content=f"tpl:{name};keys:{','.join(sorted(context.keys()))}"
            )

    monkeypatch.setattr(router, "get_templates", lambda: _FakeTemplates())


def test_get_card_sets_returns_service_result(monkeypatch):
    """卡包系列接口应透传 service 返回。"""
    monkeypatch.setattr(router, "list_card_sets", lambda: [{"code": "A1"}])
    result = asyncio.run(router.get_card_sets())
    assert result == [{"code": "A1"}]


def test_get_boosters_options_renders_partial(monkeypatch):
    """补充包选项接口应返回 options partial。"""
    _patch_templates(monkeypatch)
    monkeypatch.setattr(router, "list_set_boosters", lambda _set_code: ["Pikachu"])

    response = asyncio.run(
        router.get_boosters_options(
            request=_build_request("GET"),
            pack_code="A1",
        )
    )
    assert response.status_code == 200
    assert "tpl:partials/options_boosters.html" in bytes(response.body).decode("utf-8")


def test_save_account_pack_config_returns_account_list_and_close_modal(monkeypatch):
    """保存配置后应刷新账号列表并触发 closeModal。"""
    _patch_templates(monkeypatch)

    async def _fake_form():
        return SimpleNamespace(
            get=lambda key, default=None: {
                "pack_code": "A1",
                "booster_name": "Pikachu",
            }.get(key, default)
        )

    request = _build_request("POST")
    request.form = _fake_form  # type: ignore[method-assign]

    called = {}

    def _fake_save_account_pack_config(account_id, pack_code, booster_name):
        called["account_id"] = account_id
        called["pack_code"] = pack_code
        called["booster_name"] = booster_name

    monkeypatch.setattr(
        router, "save_account_pack_config", _fake_save_account_pack_config
    )
    monkeypatch.setattr(
        router,
        "get_accounts_context",
        lambda _session, _lang: {
            "accounts": [],
            "pack_configs": {},
            "auto_pack_map": {},
            "q": "",
            "sort_by": "id",
            "sort_order": "asc",
            "page": 0,
            "page_size": 10,
            "has_prev": False,
            "has_next": False,
            "total_items": 0,
            "t": {},
            "current_lang": "zh_CN",
        },
    )

    response = asyncio.run(
        router.save_account_pack_config_api(
            request=request,
            account_id=3,
            lang="zh_CN",
            session=object(),
        )
    )

    assert response.status_code == 200
    assert called == {"account_id": 3, "pack_code": "A1", "booster_name": "Pikachu"}
    assert response.headers.get("HX-Trigger") == "closeModal"
