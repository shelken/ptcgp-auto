# -*- coding: utf-8 -*-
"""owned_cards router 单元测试。"""

import asyncio
import json
from types import SimpleNamespace

from starlette.requests import Request
from starlette.responses import HTMLResponse

from ptcgp_auto_v2.web.routers import owned_cards as router


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


def test_get_owned_cards_returns_empty_when_items_empty_and_page_gt_zero(monkeypatch):
    """非第一页且 items 为空时应返回空串。"""
    monkeypatch.setattr(
        router,
        "build_owned_cards_list_context",
        lambda *args, **kwargs: {"items": []},
    )

    response = asyncio.run(
        router.get_owned_cards(
            request=_build_request("GET"),
            page=1,
            page_size=60,
            account_id=None,
            rarity=[],
            card_type=[],
            set_code=[],
            pack_name=[],
            element=[],
            sort_by="acquired",
            session=object(),
        )
    )

    assert response == ""


def test_get_owned_card_modal_returns_404_when_not_found(monkeypatch):
    """卡牌详情不存在时应返回 404。"""
    monkeypatch.setattr(
        router, "build_owned_card_modal_context", lambda *args, **kwargs: None
    )

    response = asyncio.run(
        router.get_owned_card_modal(
            request=_build_request("GET"),
            card_id=999,
            session=object(),
        )
    )

    assert response.status_code == 404


def test_create_exchange_request_success_sets_close_modal_and_enqueue_task(monkeypatch):
    """创建交换请求成功时应触发 closeModal 并确保任务入队。"""
    request = _build_request("POST")

    async def _fake_form():
        return SimpleNamespace(
            get=lambda key, default=None: {
                "from_account_id": "1",
                "to_account_id": "2",
                "to_friend_id": "F001",
                "target_card_id": "100",
                "target_card_rarity": "SR",
            }.get(key, default)
        )

    request.form = _fake_form  # type: ignore[method-assign]

    captured = {}

    def _fake_create_exchange_request_with_task(**kwargs):
        captured.update(kwargs)
        return True

    monkeypatch.setattr(
        router,
        "create_exchange_request_with_task",
        _fake_create_exchange_request_with_task,
    )
    monkeypatch.setattr(
        router,
        "get_translations",
        lambda _lang: {"msg_exchange_request_created": "创建成功"},
    )

    response = asyncio.run(router.create_exchange_request(request=request))

    assert response.status_code == 204
    assert captured == {
        "from_account_id": 1,
        "to_account_id": 2,
        "to_friend_id": "F001",
        "target_card_id": 100,
        "target_card_rarity": "SR",
    }
    trigger = json.loads(response.headers["HX-Trigger"])
    assert trigger["closeModal"] is True
    assert trigger["showToast"]["message"] == "创建成功"


def test_create_exchange_request_failure_sets_failed_toast(monkeypatch):
    """创建交换请求失败时应返回失败提示。"""
    request = _build_request("POST")

    async def _fake_form():
        return SimpleNamespace(
            get=lambda key, default=None: {
                "from_account_id": "",
                "to_account_id": "",
                "to_friend_id": "",
                "target_card_id": "",
                "target_card_rarity": "",
            }.get(key, default)
        )

    request.form = _fake_form  # type: ignore[method-assign]

    monkeypatch.setattr(
        router,
        "get_translations",
        lambda _lang: {"msg_exchange_request_skipped": "创建失败"},
    )

    response = asyncio.run(router.create_exchange_request(request=request))

    assert response.status_code == 204
    trigger = json.loads(response.headers["HX-Trigger"])
    assert trigger["showToast"]["message"] == "创建失败"
