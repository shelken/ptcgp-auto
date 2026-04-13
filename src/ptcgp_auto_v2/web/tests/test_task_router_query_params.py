# -*- coding: utf-8 -*-
"""任务路由查询参数解析回归测试。"""

from ptcgp_auto_v2.core.scheduling_service import TASK_SORT_BY_DISPATCH_PRIORITY
from ptcgp_auto_v2.web.routers.react_api_resources_tasks import (
    _build_task_filter_params,
    _build_task_list_query_params,
)


def test_build_task_filter_params_normalizes_filter_scope() -> None:
    params = _build_task_filter_params(
        {
            "status": ["pending", "", None, "completed"],
            "task_type": ["open_pack", "", 1, "send_gift"],
            "account_id": "12",
            "account_q": "  ash  ",
        }
    )

    assert params == {
        "status": ["pending", "completed"],
        "task_type": ["open_pack", "send_gift"],
        "account_id": 12,
        "account_q": "ash",
    }


def test_build_task_list_query_params_normalizes_sort_and_pagination() -> None:
    params = _build_task_list_query_params(
        {
            "status": ["pending"],
            "task_type": ["open_pack"],
            "account_id": "7",
            "account_q": " brock ",
            "sort_by": "unknown_field",
            "sort_order": "desc",
            "page": "-5",
            "page_size": "999",
        }
    )

    assert params == {
        "status": ["pending"],
        "task_type": ["open_pack"],
        "account_id": 7,
        "account_q": "brock",
        "sort_by": TASK_SORT_BY_DISPATCH_PRIORITY,
        "sort_order": "asc",
        "page": 0,
        "page_size": 100,
    }


def test_build_task_list_query_params_uses_defaults_for_missing_values() -> None:
    params = _build_task_list_query_params({})

    assert params == {
        "status": [],
        "task_type": [],
        "account_id": None,
        "account_q": "",
        "sort_by": TASK_SORT_BY_DISPATCH_PRIORITY,
        "sort_order": "asc",
        "page": 0,
        "page_size": 10,
    }
