# -*- coding: utf-8 -*-
"""账号与计划路由参数解析回归测试。"""

from ptcgp_auto_v2.web.routers.react_api_accounts_plans import (
    _build_basic_list_query_params,
)


def test_build_basic_list_query_params_normalizes_basic_fields() -> None:
    params = _build_basic_list_query_params(
        {
            "q": " ash ",
            "sort_by": "nickname",
            "sort_order": "desc",
            "page": "-3",
            "page_size": "999",
        },
        default_sort_by="id",
        default_sort_order="asc",
        default_page_size=10,
    )

    assert params == {
        "q": " ash ",
        "sort_by": "nickname",
        "sort_order": "desc",
        "page": -3,
        "page_size": 999,
    }


def test_build_basic_list_query_params_uses_defaults() -> None:
    params = _build_basic_list_query_params(
        {},
        default_sort_by="id",
        default_sort_order="asc",
        default_page_size=10,
    )

    assert params == {
        "q": "",
        "sort_by": "id",
        "sort_order": "asc",
        "page": 0,
        "page_size": 10,
    }
