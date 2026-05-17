# -*- coding: utf-8 -*-
"""开包记录查询状态回归测试。"""

from ptcgp_auto_v2.web.services.record_service import build_records_list_query_state


def test_build_records_list_query_state_normalizes_filters_and_pagination() -> None:
    state = build_records_list_query_state(
        page=-3,
        page_size=999,
        rarity=[" SR ", "", None, "AR"],  # type: ignore[list-item]
        card_type=[" fire ", " ", "water"],
        set_code=[" A1 ", " ", "A2"],
        card_name_query="  皮卡丘  ",
    )

    assert state.page == 0
    assert state.page_size == 100
    assert state.rarity == ["SR", "AR"]
    assert state.card_type == ["fire", "water"]
    assert state.set_code == ["A1", "A2"]
    assert state.card_name_query == "皮卡丘"


def test_build_records_list_query_state_uses_defaults() -> None:
    state = build_records_list_query_state()

    assert state.page == 0
    assert state.page_size == 10
    assert state.rarity == []
    assert state.card_type == []
    assert state.set_code == []
    assert state.card_name_query == ""
