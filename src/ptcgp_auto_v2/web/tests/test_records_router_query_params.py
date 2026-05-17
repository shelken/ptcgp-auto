# -*- coding: utf-8 -*-
"""开包记录路由参数解析回归测试。"""

from ptcgp_auto_v2.web.routers.react_api_records import _build_records_query_params


def test_build_records_query_params_normalizes_filters_and_pagination() -> None:
    params = _build_records_query_params(
        {
            "page": "-3",
            "page_size": "999",
            "rarity": [" SR ", "", None, "AR"],
            "card_type": [" fire ", " ", "water"],
            "set_code": [" A1 ", " ", "A2"],
            "q": "  皮卡丘  ",
        }
    )

    assert params == {
        "page": 0,
        "page_size": 100,
        "rarity": ["SR", "AR"],
        "card_type": ["fire", "water"],
        "set_code": ["A1", "A2"],
        "card_name_query": "皮卡丘",
    }


def test_build_records_query_params_uses_defaults() -> None:
    params = _build_records_query_params({})

    assert params == {
        "page": 0,
        "page_size": 10,
        "rarity": [],
        "card_type": [],
        "set_code": [],
        "card_name_query": "",
    }
