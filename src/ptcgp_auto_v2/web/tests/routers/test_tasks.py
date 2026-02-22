# -*- coding: utf-8 -*-
"""tasks router 单元测试。"""

import asyncio
import json
from types import SimpleNamespace
from typing import cast

from starlette.requests import Request
from starlette.responses import HTMLResponse

from ptcgp_auto_v2.web.routers import tasks as router


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


def _patch_task_dependencies(monkeypatch):
    """设置 tasks 路由常用依赖替身。"""
    monkeypatch.setattr(
        router, "TaskRegistry", SimpleNamespace(all_types=lambda: ["open_pack"])
    )
    monkeypatch.setattr(router, "TaskStatus", [SimpleNamespace(value="pending")])
    monkeypatch.setattr(
        router,
        "AccountRepository",
        lambda: SimpleNamespace(get_all=lambda: [SimpleNamespace(id=1)]),
    )
    monkeypatch.setattr(router, "build_tasks_page_url", lambda *args, **kwargs: "/p")
    monkeypatch.setattr(router, "get_translations", lambda _lang: {})


def test_reset_completed_tasks_success_sets_done_toast(monkeypatch):
    """重置成功时应返回 done toast。"""
    _patch_templates(monkeypatch)

    async def _fake_form():
        return SimpleNamespace(
            getlist=lambda key: {
                "status": ["completed"],
                "task_type": ["open_pack"],
            }.get(key, []),
            get=lambda key, default=None: {
                "account_id": "1",
                "sort_by": "dispatch_priority",
                "sort_order": "asc",
            }.get(key, default),
        )

    request = _build_request("POST")
    request.form = _fake_form  # type: ignore[method-assign]

    monkeypatch.setattr(router, "normalize_task_sort", lambda a, b: (a, b))
    monkeypatch.setattr(router, "reset_completed_tasks_by_filters", lambda **_kwargs: 3)
    monkeypatch.setattr(
        router,
        "list_task_status_view",
        lambda **_kwargs: ([SimpleNamespace(status="pending")], False),
    )
    monkeypatch.setattr(
        router,
        "get_translations",
        lambda _lang: {"msg_reset_completed_done": "已重置 {count} 个任务"},
    )

    response = asyncio.run(
        router.reset_completed_tasks(
            request=request,
            lang="zh_CN",
            session=object(),
        )
    )

    html_response = cast(HTMLResponse, response)
    assert html_response.status_code == 200
    trigger = json.loads(response.headers["HX-Trigger"])
    assert trigger["showToast"]["message"] == "已重置 3 个任务"


def test_reset_completed_tasks_empty_sets_empty_toast(monkeypatch):
    """无可重置任务时应返回 empty toast。"""
    _patch_templates(monkeypatch)

    async def _fake_form():
        return SimpleNamespace(
            getlist=lambda _key: [],
            get=lambda _key, default=None: default,
        )

    request = _build_request("POST")
    request.form = _fake_form  # type: ignore[method-assign]

    monkeypatch.setattr(
        router, "normalize_task_sort", lambda _a, _b: ("dispatch_priority", "asc")
    )
    monkeypatch.setattr(router, "reset_completed_tasks_by_filters", lambda **_kwargs: 0)
    monkeypatch.setattr(router, "list_task_status_view", lambda **_kwargs: ([], False))
    monkeypatch.setattr(
        router,
        "get_translations",
        lambda _lang: {"msg_reset_completed_empty": "没有需要重置的任务"},
    )

    response = asyncio.run(
        router.reset_completed_tasks(
            request=request,
            lang="zh_CN",
            session=object(),
        )
    )

    html_response = cast(HTMLResponse, response)
    assert html_response.status_code == 200
    trigger = json.loads(response.headers["HX-Trigger"])
    assert trigger["showToast"]["message"] == "没有需要重置的任务"


def test_get_tasks_returns_empty_string_when_page_has_no_data(monkeypatch):
    """分页页码大于 0 且无数据时应返回空串。"""
    _patch_task_dependencies(monkeypatch)
    monkeypatch.setattr(
        router, "normalize_task_sort", lambda _a, _b: ("next_run_at", "desc")
    )
    monkeypatch.setattr(router, "list_task_status_view", lambda **_kwargs: ([], False))

    response = asyncio.run(
        router.get_tasks(
            request=_build_request("GET"),
            page=2,
            page_size=10,
            status=[],
            task_type=[],
            account_id=None,
            sort_by="x",
            sort_order="x",
            lang="zh_CN",
            session=object(),
        )
    )

    assert response == ""


def test_get_tasks_uses_normalized_sort_for_query(monkeypatch):
    """任务列表查询应使用归一化后的排序参数。"""
    _patch_templates(monkeypatch)
    _patch_task_dependencies(monkeypatch)

    captured = {}

    def _fake_normalize_task_sort(_a, _b):
        return "next_run_at", "asc"

    def _fake_list_task_status_view(**kwargs):
        captured["sort_by"] = kwargs["sort_by"]
        captured["sort_order"] = kwargs["sort_order"]
        return [SimpleNamespace(status="pending")], False

    monkeypatch.setattr(router, "normalize_task_sort", _fake_normalize_task_sort)
    monkeypatch.setattr(router, "list_task_status_view", _fake_list_task_status_view)

    response = asyncio.run(
        router.get_tasks(
            request=_build_request("GET"),
            page=0,
            page_size=10,
            status=[],
            task_type=[],
            account_id=None,
            sort_by="bad",
            sort_order="bad",
            lang="zh_CN",
            session=object(),
        )
    )

    html_response = cast(HTMLResponse, response)
    assert html_response.status_code == 200
    assert captured == {"sort_by": "next_run_at", "sort_order": "asc"}
