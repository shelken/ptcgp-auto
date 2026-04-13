# -*- coding: utf-8 -*-
"""通知路由查询参数解析回归测试。"""

from ptcgp_auto_v2.web.routers.react_api_notifications import (
    _build_notification_list_query_params,
    _build_notification_scope_params,
)


def test_build_notification_scope_params_normalizes_scene_and_account() -> None:
    params = _build_notification_scope_params(
        {
            "scene": "unknown-scene",
            "account_id": "12",
        }
    )

    assert params == {
        "scene": None,
        "account_id": 12,
    }


def test_build_notification_list_query_params_normalizes_list_state() -> None:
    params = _build_notification_list_query_params(
        {
            "scene": "task_status",
            "account_id": "7",
            "is_read": "true",
            "q": " hello ",
            "sort_by": "title",
            "sort_order": "asc",
            "page": "-5",
            "page_size": "999",
        }
    )

    assert params == {
        "scene": "task_status",
        "account_id": 7,
        "is_read": True,
        "q": " hello ",
        "sort_by": "title",
        "sort_order": "asc",
        "page": 0,
        "page_size": 100,
    }


def test_build_notification_list_query_params_uses_defaults_for_missing_values() -> None:
    params = _build_notification_list_query_params({})

    assert params == {
        "scene": None,
        "account_id": None,
        "is_read": None,
        "q": "",
        "sort_by": "created_at",
        "sort_order": "desc",
        "page": 0,
        "page_size": 10,
    }
