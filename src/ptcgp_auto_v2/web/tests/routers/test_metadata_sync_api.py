# -*- coding: utf-8 -*-
"""metadata sync API 路由测试。"""

from __future__ import annotations

import asyncio
from types import SimpleNamespace

from starlette.requests import Request

from ptcgp_auto_v2.web.routers import metadata as router


def _build_request(method: str = "GET", body: dict[str, str] | None = None) -> Request:
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

    request = Request(scope, receive)
    if body is not None:

        async def _fake_form():
            return SimpleNamespace(get=lambda key, default=None: body.get(key, default))

        request.form = _fake_form  # type: ignore[method-assign]
    return request


def _fake_context(**kwargs):
    """统一伪造模板上下文。"""
    return {
        "t": {},
        "current_lang": "zh_CN",
        "sets": [],
        "packs_by_set": {},
        "sync_check": {},
        "selected_node_type": kwargs.get("selected_node_type", "root"),
        "selected_node_id": kwargs.get("selected_node_id", "all"),
        "selected_set_code": kwargs.get("selected_set_code", ""),
        "selected_pack_name": kwargs.get("selected_pack_name", ""),
        "selected_card_key": "",
        "selected_pack_cards": [],
        "ui_step": kwargs.get("ui_step", 1),
    }


def test_sync_preview_api_returns_preview_id(monkeypatch):
    """预览接口应返回快照 ID。"""

    monkeypatch.setattr(
        router,
        "render_template",
        lambda _request, _template, context: router.HTMLResponse(
            content=str(context.get("sync_preview", {})), status_code=200
        ),
    )
    monkeypatch.setattr(
        router,
        "build_metadata_context",
        lambda **kwargs: _fake_context(**kwargs),
    )
    monkeypatch.setattr(
        router,
        "preview_metadata_sync",
        lambda **_kwargs: {"snapshot_id": "snp-1", "summary": {"upsert_sets": 1}},
    )

    response = asyncio.run(
        router.preview_metadata_sync_api(
            request=_build_request(
                "POST",
                {
                    "node_type": "set",
                    "node_id": "A1",
                    "action": "sync_force",
                    "ui_step": "2",
                    "selected_set_code": "A1",
                    "selected_pack_name": "",
                    "force_refresh": "0",
                },
            ),
        )
    )

    assert response.status_code == 200
    assert b"snp-1" in response.body


def test_sync_execute_api_returns_error_when_snapshot_missing(monkeypatch):
    """执行接口在快照缺失时应返回 400。"""

    def _raise(*_args, **_kwargs):
        raise ValueError("快照不存在或已过期")

    monkeypatch.setattr(router, "execute_metadata_sync", _raise)

    response = asyncio.run(
        router.execute_metadata_sync_api(
            request=_build_request("POST", {"snapshot_id": "x", "ui_step": "3"}),
                    )
    )

    assert response.status_code == 400
    assert "快照" in bytes(response.body).decode("utf-8")


def test_sync_check_api_refreshes_context(monkeypatch):
    """检查接口应刷新 sync_check 并返回模板。"""

    monkeypatch.setattr(
        router,
        "render_template",
        lambda _request, _template, context: router.HTMLResponse(
            content=str(context.get("sync_check", {})), status_code=200
        ),
    )
    monkeypatch.setattr(
        router,
        "build_metadata_context",
        lambda **kwargs: _fake_context(**kwargs),
    )
    monkeypatch.setattr(
        router,
        "check_metadata_sources",
        lambda: {
            "local": {"sets": 1},
            "flibustier": {"sets": 2},
            "poke52": {"series": 2},
        },
    )

    response = asyncio.run(
        router.check_metadata_sync_api(
            request=_build_request("POST", {"ui_step": "1"}),
                    )
    )

    assert response.status_code == 200
    assert "local" in bytes(response.body).decode("utf-8")


def test_select_node_api_refreshes_selected_context(monkeypatch):
    """节点选择接口应将节点上下文带回模板。"""

    monkeypatch.setattr(
        router,
        "render_template",
        lambda _request, _template, context: router.HTMLResponse(
            content=f"{context.get('selected_node_type')}|{context.get('selected_node_id')}",
            status_code=200,
        ),
    )
    monkeypatch.setattr(
        router,
        "build_metadata_context",
        lambda **kwargs: _fake_context(**kwargs),
    )

    response = asyncio.run(
        router.select_metadata_node_api(
            request=_build_request(
                "POST",
                {
                    "node_type": "pack",
                    "node_id": "PackA",
                    "selected_set_code": "A1",
                    "selected_pack_name": "PackA",
                    "ui_step": "1",
                },
            ),
        )
    )

    assert response.status_code == 200
    assert "pack|PackA" in bytes(response.body).decode("utf-8")


def test_sync_preview_api_uses_node_action_params(monkeypatch):
    """预览接口应转发 node/action 协议参数。"""
    captured: dict[str, str] = {}

    monkeypatch.setattr(
        router,
        "render_template",
        lambda _request, _template, context: router.HTMLResponse(
            content=str(context.get("sync_preview", {})), status_code=200
        ),
    )
    monkeypatch.setattr(
        router,
        "build_metadata_context",
        lambda **kwargs: _fake_context(**kwargs),
    )

    def _fake_preview(**kwargs):
        captured.update(
            {
                "node_type": kwargs["node_type"],
                "node_id": kwargs["node_id"],
                "action": kwargs["action"],
            }
        )
        return {"snapshot_id": "snp-node", "summary": {}}

    monkeypatch.setattr(router, "preview_metadata_sync", _fake_preview)

    response = asyncio.run(
        router.preview_metadata_sync_api(
            request=_build_request(
                "POST",
                {
                    "node_type": "pack",
                    "node_id": "PackA",
                    "action": "localize_supplement",
                    "selected_set_code": "A1",
                    "selected_pack_name": "PackA",
                    "ui_step": "2",
                    "force_refresh": "1",
                },
            ),
        )
    )

    assert response.status_code == 200
    assert captured == {
        "node_type": "pack",
        "node_id": "PackA",
        "action": "localize_supplement",
    }
