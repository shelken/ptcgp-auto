# -*- coding: utf-8 -*-
"""好友路由参数解析回归测试。"""

from ptcgp_auto_v2.web.routers.react_api_friendships import (
    _build_friendship_action_params,
    _build_friendship_list_query_params,
)


def test_build_friendship_list_query_params_normalizes_split_list_state() -> None:
    params = _build_friendship_list_query_params(
        {
            "account_id": "7",
            "from_account_id": "12",
            "q": " ash ",
            "sort_by": "created_at",
            "sort_order": "desc",
            "page": "2",
            "page_size": "20",
            "request_sort_by": "from_account_id",
            "request_sort_order": "asc",
            "request_page": "-3",
            "request_page_size": "999",
            "friendship_sort_by": "account_id",
            "friendship_sort_order": "desc",
            "friendship_page": "1",
            "friendship_page_size": "50",
        }
    )

    assert params == {
        "account_id": 7,
        "from_account_id": 12,
        "q": " ash ",
        "sort_by": "created_at",
        "sort_order": "desc",
        "page": 2,
        "page_size": 20,
        "request_sort_by": "from_account_id",
        "request_sort_order": "asc",
        "request_page": -3,
        "request_page_size": 999,
        "friendship_sort_by": "account_id",
        "friendship_sort_order": "desc",
        "friendship_page": 1,
        "friendship_page_size": 50,
    }


def test_build_friendship_action_params_normalizes_ids_and_target_field() -> None:
    params = _build_friendship_action_params(
        {
            "from_account_id": "5",
            "to_account_id": "9",
            "to_friend_id": " 1234567890123456 ",
        },
        target_field="to_friend_id",
    )

    assert params == {
        "from_account_id": 5,
        "to_account_id": 9,
        "target_value": "1234567890123456",
    }


def test_build_friendship_action_params_uses_empty_target_for_missing_value() -> None:
    params = _build_friendship_action_params(
        {
            "from_account_id": "5",
            "to_account_id": None,
        },
        target_field="friend_id",
    )

    assert params == {
        "from_account_id": 5,
        "to_account_id": None,
        "target_value": "",
    }
