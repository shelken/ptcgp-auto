# -*- coding: utf-8 -*-
"""交换卡牌路由参数解析回归测试。"""

from ptcgp_auto_v2.web.routers.react_api_exchange_cards import (
    _build_exchange_card_create_params,
    _build_exchange_card_list_query_params,
)


def test_build_exchange_card_create_params_normalizes_create_payload() -> None:
    params = _build_exchange_card_create_params(
        {
            "from_account_id": "5",
            "to_account_id": "9",
            "target_card_id": "101",
            "to_friend_id": " 1234567890123456 ",
            "target_card_rarity": "SR",
        }
    )

    assert params == {
        "from_account_id": 5,
        "to_account_id": 9,
        "target_card_id": 101,
        "to_friend_id": "1234567890123456",
        "target_card_rarity": "SR",
    }


def test_build_exchange_card_list_query_params_normalizes_list_scope() -> None:
    params = _build_exchange_card_list_query_params(
        {
            "account_id": "7",
            "status": "",
            "q": " mewtwo ",
            "sort_by": "created_at",
            "sort_order": "desc",
            "page": "-5",
            "page_size": "999",
        }
    )

    assert params == {
        "account_id": 7,
        "status": None,
        "q": " mewtwo ",
        "sort_by": "created_at",
        "sort_order": "desc",
        "page": -5,
        "page_size": 999,
    }


def test_build_exchange_card_list_query_params_uses_defaults() -> None:
    params = _build_exchange_card_list_query_params({})

    assert params == {
        "account_id": None,
        "status": None,
        "q": "",
        "sort_by": "created_at",
        "sort_order": "desc",
        "page": 0,
        "page_size": 10,
    }
