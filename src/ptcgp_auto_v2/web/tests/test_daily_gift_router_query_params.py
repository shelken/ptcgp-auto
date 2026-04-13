# -*- coding: utf-8 -*-
"""每日送卡路由参数解析回归测试。"""

from ptcgp_auto_v2.web.routers.react_api_metadata_daily_gift import (
    _build_daily_gift_query_params,
)


def test_build_daily_gift_query_params_normalizes_shared_and_pair_params() -> None:
    params = _build_daily_gift_query_params(
        {
            "biz_date_local": "2026-04-14",
            "account_id": "7",
            "sort_by": "updated_at",
            "sort_order": "desc",
            "page": "-3",
            "page_size": "999",
            "pair_page": "2",
            "pair_page_size": "50",
        }
    )

    assert params == {
        "biz_date_local": "2026-04-14",
        "account_id": 7,
        "sort_by": "updated_at",
        "sort_order": "desc",
        "page": -3,
        "page_size": 999,
        "pair_page": 2,
        "pair_page_size": 50,
    }


def test_build_daily_gift_query_params_uses_defaults() -> None:
    params = _build_daily_gift_query_params({})

    assert params == {
        "biz_date_local": None,
        "account_id": None,
        "sort_by": "updated_at",
        "sort_order": "desc",
        "page": 0,
        "page_size": 10,
        "pair_page": 0,
        "pair_page_size": 10,
    }
