# -*- coding: utf-8 -*-
"""metadata 同步流程回归测试。"""

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


def _patch_template(monkeypatch):
    """替换模板响应，便于断言上下文。"""

    monkeypatch.setattr(
        router,
        "render_template",
        lambda _request, _template, context: router.HTMLResponse(
            content=str(context), status_code=200
        ),
    )
    monkeypatch.setattr(
        router,
        "build_metadata_context",
        lambda **_kwargs: {
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


def test_preview_then_execute_flow_success(monkeypatch):
    """预览后执行应串联成功。"""
    _patch_template(monkeypatch)

    monkeypatch.setattr(
        router,
        "preview_metadata_sync",
        lambda **_kwargs: {
            "snapshot_id": "snap-ok",
            "summary": {"upsert_sets": 1},
            "payload": {},
        },
    )
    monkeypatch.setattr(
        router,
        "execute_metadata_sync",
        lambda snapshot_id: {
            "snapshot_id": snapshot_id,
            "flibustier": {"upsert_sets": 1},
            "localization": {"set_label_updates": 1},
        },
    )

    preview_resp = asyncio.run(
        router.preview_metadata_sync_api(
            request=_build_request(
                "POST",
                {
                    "node_type": "root",
                    "node_id": "all",
                    "action": "update_data_supplement",
                    "ui_step": "2",
                    "selected_set_code": "",
                    "selected_pack_name": "",
                    "force_refresh": "0",
                },
            ),
        )
    )
    assert preview_resp.status_code == 200
    assert "snap-ok" in bytes(preview_resp.body).decode("utf-8")
    assert "'ui_step': 2" in bytes(preview_resp.body).decode("utf-8")

    execute_resp = asyncio.run(
        router.execute_metadata_sync_api(
            request=_build_request(
                "POST",
                {
                    "snapshot_id": "snap-ok",
                    "ui_step": "3",
                    "node_type": "root",
                    "node_id": "all",
                    "selected_set_code": "",
                    "selected_pack_name": "",
                },
            ),
        )
    )
    assert execute_resp.status_code == 200
    assert "set_label_updates" in bytes(execute_resp.body).decode("utf-8")
    assert "'ui_step': 1" in bytes(execute_resp.body).decode("utf-8")


def test_execute_flow_rejects_expired_snapshot(monkeypatch):
    """执行时快照过期应返回 400。"""

    def _raise(_snapshot_id: str):
        raise ValueError("快照不存在或已过期")

    monkeypatch.setattr(router, "execute_metadata_sync", _raise)

    response = asyncio.run(
        router.execute_metadata_sync_api(
            request=_build_request(
                "POST", {"snapshot_id": "snap-expired", "ui_step": "3"}
            ),
        )
    )
    assert response.status_code == 400
    assert "过期" in bytes(response.body).decode("utf-8")
