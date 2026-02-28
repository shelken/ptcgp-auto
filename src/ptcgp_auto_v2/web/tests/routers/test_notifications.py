# -*- coding: utf-8 -*-
"""notifications router 单元测试（无 httpx 依赖）。"""

import asyncio
from types import SimpleNamespace
from urllib.parse import urlencode

from starlette.requests import Request
from starlette.responses import HTMLResponse
from sqlmodel import Session

from ptcgp_auto_v2.db.models import Card, Notification
from ptcgp_auto_v2.web.routers import notifications as router


def _build_request(method: str = "GET", query: dict | None = None) -> Request:
    """构建最小 Request 对象。"""
    scope = {
        "type": "http",
        "method": method,
        "path": "/",
        "query_string": urlencode(query or {}).encode("utf-8"),
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


def test_parse_is_read_filter_values():
    """is_read 字符串应被标准化为布尔值或 None。"""
    assert router._parse_is_read_filter("true") is True
    assert router._parse_is_read_filter("false") is False
    assert router._parse_is_read_filter(None) is None
    assert router._parse_is_read_filter("other") is None


def test_parse_unique_int_ids_deduplicates_and_skips_invalid():
    """ID 解析应去重并过滤非法值。"""
    assert router._parse_unique_int_ids(["101", "x", "101", "202"]) == [101, 202]


def test_build_notification_list_filters_normalizes_values():
    """列表过滤参数应统一做容错与范围归一化。"""
    normalized = router._build_notification_list_filters(
        scene="invalid_scene",
        account_id="not-int",
        is_read="true",
        q=" keyword ",
        sort_by="created_at",
        sort_order="desc",
        page=-3,
        page_size=999,
    )

    assert normalized["scene"] is None
    assert normalized["account_id"] is None
    assert normalized["is_read"] is True
    assert normalized["q"] == " keyword "
    assert normalized["page"] == 0
    assert normalized["page_size"] == 100


def test_get_notifications_page_returns_notification_template(
    session: Session, monkeypatch
):
    """通知主页面应返回 notification_page 模板。"""
    _patch_render_template(monkeypatch)
    request = _build_request("GET")

    response = asyncio.run(
        router.get_notifications_page(
            request=request,
            scene=None,
            account_id=None,
            is_read=None,
            q="",
            sort_by="created_at",
            sort_order="desc",
            page=0,
            page_size=10,
            session=session,
        )
    )

    assert response.status_code == 200
    assert "tpl:partials/notification_page.html" in bytes(response.body).decode("utf-8")


def test_get_notifications_list_returns_list_template(session: Session, monkeypatch):
    """通知列表接口应返回 notification_list 模板。"""
    _patch_render_template(monkeypatch)
    request = _build_request("GET")

    response = asyncio.run(
        router.get_notifications_list(
            request=request,
            scene=None,
            account_id=None,
            is_read=None,
            q="",
            sort_by="created_at",
            sort_order="desc",
            page=0,
            page_size=10,
            session=session,
        )
    )

    assert response.status_code == 200
    assert "tpl:partials/notification_page.html" in bytes(response.body).decode("utf-8")


def test_mark_all_read_triggers_toast_header(session: Session, monkeypatch):
    """全部已读应返回提示事件头。"""
    _patch_render_template(monkeypatch)
    session.add(
        Notification(scene="task_status", title="n1", content="c1", is_read=False)
    )
    session.commit()
    request = _build_request("POST")

    response = asyncio.run(
        router.mark_all_as_read(
            request=request,
            scene=None,
            account_id=None,
            is_read=None,
            q="",
            sort_by="created_at",
            sort_order="desc",
            page=0,
            page_size=10,
            session=session,
        )
    )

    assert response.status_code == 200
    assert "HX-Trigger" in response.headers
    assert "notificationsUpdated" in response.headers["HX-Trigger"]


def test_update_notification_config_returns_item_partial(session: Session, monkeypatch):
    """配置更新应返回单个配置项模板片段。"""
    _patch_render_template(monkeypatch)
    from ptcgp_auto_v2.db.repositories.notification_config_repository import (
        NotificationConfigRepository,
    )

    NotificationConfigRepository().get_or_create("task_status")

    async def _fake_form():
        return SimpleNamespace(
            get=lambda key, default=None: {
                "scene": "task_status",
                "enabled": "on",
                "enabled_webhook": "on",
            }.get(key, default),
            getlist=lambda key: (
                ["open_pack"]
                if key == "notify_task_types"
                else (["failed"] if key == "notify_on" else [])
            ),
        )

    request = _build_request("POST")
    request.form = _fake_form  # type: ignore[method-assign]

    response = asyncio.run(
        router.update_notification_config(request=request, session=session)
    )

    assert response.status_code == 200
    assert "tpl:partials/notification_page.html" in bytes(response.body).decode("utf-8")

    repo = NotificationConfigRepository()
    extra = repo.get_extra_config("task_status")
    assert extra.get("notify_task_types") == ["open_pack"]
    assert extra.get("notify_on") == ["failed"]


def test_get_notification_card_picker_modal_returns_partial(
    session: Session, monkeypatch
):
    """卡牌选择弹窗接口应返回 modal 片段。"""
    _patch_render_template(monkeypatch)
    request = _build_request("GET")

    response = asyncio.run(
        router.get_notification_card_picker_modal(
            request=request,
            scene="rare_card_obtained",
            card_selector_q="",
            card_selector_rarity="",
            card_selector_set_code="",
            card_selector_pack_name="",
            card_selector_sort_by="id",
            card_selector_sort_order="asc",
            card_selector_page=0,
            card_selector_page_size=24,
            session=session,
        )
    )

    assert response.status_code == 200
    assert "tpl:partials/modals/card_picker_modal.html" in bytes(response.body).decode(
        "utf-8"
    )


def test_apply_notification_card_picker_returns_selected_partial(
    session: Session, monkeypatch
):
    """应用选择后应返回已选卡片片段并触发关闭弹窗。"""
    _patch_render_template(monkeypatch)

    async def _fake_form():
        return SimpleNamespace(
            getlist=lambda key: ["101", "101", "202"]
            if key == "notify_card_ids"
            else []
        )

    request = _build_request("POST")
    request.form = _fake_form  # type: ignore[method-assign]

    response = asyncio.run(
        router.apply_notification_card_picker(
            request=request,
            scene="rare_card_obtained",
            session=session,
        )
    )

    assert response.status_code == 200
    assert "tpl:partials/notification_page.html" in bytes(response.body).decode("utf-8")
    assert "HX-Trigger" in response.headers
    assert "closeModal" in response.headers["HX-Trigger"]


def test_send_test_webhook_returns_toast_header(session: Session, monkeypatch):
    """发送测试企微推送应返回 toast 事件头。"""
    request = _build_request("POST")
    sample = Notification(scene="task_status", title="测试标题", content="测试内容")
    session.add(sample)
    session.commit()

    class _FakeNotifier:
        def send_webhook_notification(
            self, title: str, content: str, image_url: str | None = None
        ):
            assert title == "测试标题"
            assert content == "测试内容"
            assert image_url is None
            return True

    monkeypatch.setattr(router, "get_notifier", lambda: _FakeNotifier())

    response = asyncio.run(
        router.send_test_webhook(
            request=request,
            notification_id=sample.id,
        )
    )

    assert response.status_code == 200
    assert "HX-Trigger" in response.headers
    assert "showToast" in response.headers["HX-Trigger"]


def test_send_test_webhook_uses_notification_image_for_rare_card(
    session: Session, monkeypatch
):
    """稀有卡牌测试发送应带上由通知内容解析出的卡图 URL。"""
    card = Card(
        id=260,
        number=260,
        name="Zapdos ex",
        rarity="SR",
        type="Pokemon",
        set_code="A1",
        image_url="cPK_20_001040_00_THUNDERex_SR.webp",
    )
    session.add(card)
    sample = Notification(
        scene="rare_card_obtained",
        title="稀有卡牌通知",
        content="账号: skn159\n事件: 开出稀有卡牌\n卡牌: Zapdos ex\n稀有度: SR (2星)",
        is_read=False,
    )
    session.add(sample)
    session.commit()

    request = _build_request("POST")

    class _FakeNotifier:
        def send_webhook_notification(
            self, title: str, content: str, image_url: str | None = None
        ):
            assert title == "稀有卡牌通知"
            assert "Zapdos ex" in content
            return True

    monkeypatch.setattr(router, "get_notifier", lambda: _FakeNotifier())

    response = asyncio.run(
        router.send_test_webhook(
            request=request,
            notification_id=sample.id,
            session=session,
        )
    )

    assert response.status_code == 200
