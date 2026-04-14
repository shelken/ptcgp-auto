# -*- coding: utf-8 -*-
"""拥有卡牌路由参数解析回归测试。"""

from ptcgp_auto_v2.web.routers import react_api_owned_cards
from ptcgp_auto_v2.web.routers.react_api_owned_cards import (
    _build_owned_card_detail_query_params,
    _build_owned_card_exchange_accounts_query_params,
    _build_owned_cards_list_query_params,
    _build_owned_cards_stats_query_params,
)


def test_build_owned_cards_list_query_params_normalizes_main_list_state() -> None:
    params = _build_owned_cards_list_query_params(
        {
            "page": "-3",
            "page_size": "999",
            "account_id": " 10001 ",
            "rarity": [" SR ", "", "AR"],
            "card_type": ["pokemon", " "],
            "set_code": ["A1"],
            "pack_name": [" Mewtwo "],
            "element": [" fire "],
            "sort_by": "count",
            "ownership_scope": "invalid",
        }
    )

    assert params == {
        "page": 0,
        "page_size": 100,
        "account_id": "10001",
        "rarity": ["SR", "AR"],
        "card_type": ["pokemon"],
        "set_code": ["A1"],
        "pack_name": ["Mewtwo"],
        "element": ["fire"],
        "sort_by": "count",
        "ownership_scope": "owned",
    }


def test_build_owned_cards_stats_query_params_reuses_main_filter_state() -> None:
    params = _build_owned_cards_stats_query_params(
        {
            "account_id": " 10001 ",
            "rarity": [" SR ", "AR"],
            "card_type": ["pokemon"],
            "set_code": ["A1"],
            "pack_name": [" Mewtwo "],
            "element": [" fire "],
            "ownership_scope": "missing",
        }
    )

    assert params == {
        "account_id": "10001",
        "rarity": ["SR", "AR"],
        "card_type": ["pokemon"],
        "set_code": ["A1"],
        "pack_name": ["Mewtwo"],
        "element": ["fire"],
        "ownership_scope": "missing",
    }


def test_build_owned_card_detail_query_params_normalizes_scope_and_page_size() -> None:
    params = _build_owned_card_detail_query_params(
        {
            "ownership_state": "all",
            "page_size": "999",
        }
    )

    assert params == {
        "ownership_scope": "all",
        "page_size": 50,
    }


def test_build_owned_card_exchange_accounts_query_params_normalizes_list_scope() -> None:
    params = _build_owned_card_exchange_accounts_query_params(
        {
            "page": "-9",
            "page_size": "999",
            "q": " ash ",
            "sort_by": "invalid_field",
            "sort_order": "sideways",
        }
    )

    assert params == {
        "page": 0,
        "page_size": 50,
        "q": "ash",
        "sort_by": "account_id",
        "sort_order": "asc",
    }


def test_owned_card_detail_route_exposes_unified_ownership_scope_query() -> None:
    detail_route = next(
        route
        for route in react_api_owned_cards.router.routes
        if getattr(route, "path", "") == "/owned-cards/{card_id}/detail"
    )

    query_param_names = [param.name for param in detail_route.dependant.query_params]

    assert "ownership_scope" in query_param_names
