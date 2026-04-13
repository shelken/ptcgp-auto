# -*- coding: utf-8 -*-
"""通知路由查询参数解析回归测试。"""

from ptcgp_auto_v2.web.routers.react_api_notifications import (
    _build_notification_card_picker_query_params,
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


def test_build_notification_card_picker_query_params_normalizes_scope_and_pagination() -> None:
    params = _build_notification_card_picker_query_params(
        {
            "scene": "unknown-scene",
            "card_selector_q": " pika ",
            "card_selector_rarity": "crown",
            "card_selector_set_code": "A2",
            "card_selector_pack_name": "Mew",
            "card_selector_sort_by": "name",
            "card_selector_sort_order": "desc",
            "card_selector_page": "-3",
            "card_selector_page_size": "999",
        },
        selected_card_ids=[9, 3],
    )

    assert params == {
        "scene": "rare_card_obtained",
        "selected_card_ids": [9, 3],
        "q": " pika ",
        "rarity": "crown",
        "set_code": "A2",
        "pack_name": "Mew",
        "sort_by": "name",
        "sort_order": "desc",
        "page": 0,
        "page_size": 60,
    }


def test_build_notification_card_picker_query_params_uses_defaults() -> None:
    params = _build_notification_card_picker_query_params({}, selected_card_ids=[])

    assert params == {
        "scene": "rare_card_obtained",
        "selected_card_ids": [],
        "q": "",
        "rarity": "",
        "set_code": "",
        "pack_name": "",
        "sort_by": "id",
        "sort_order": "asc",
        "page": 0,
        "page_size": 24,
    }
