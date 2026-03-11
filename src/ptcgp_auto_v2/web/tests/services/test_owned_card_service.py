# -*- coding: utf-8 -*-

"""owned_card_service 列表上下文测试。"""

from ptcgp_auto_v2.web.services.owned_card_service import (
    build_owned_cards_list_context,
    build_owned_cards_progress_context,
)


def test_build_owned_cards_list_context_passes_account_query(monkeypatch) -> None:
    """拥有卡牌列表应透传账号搜索词，而不是强制转成整数。"""
    captured: dict[str, object] = {}

    def _fake_list_owned_cards(self, **kwargs):
        captured.update(kwargs)
        return []

    monkeypatch.setattr(
        "ptcgp_auto_v2.web.services.owned_card_service.AccountCardRepository.list_owned_cards",
        _fake_list_owned_cards,
    )
    monkeypatch.setattr(
        "ptcgp_auto_v2.web.services.owned_card_service.AccountCardRepository.count_cards_by_scope",
        lambda self, **kwargs: 0,
    )

    context = build_owned_cards_list_context(
        session=None,
        page=0,
        page_size=10,
        account_id="rbksh2",
        ownership_scope="missing",
    )

    assert context["items"] == []
    assert captured["account_query"] == "rbksh2"
    assert captured["ownership_scope"] == "missing"


def test_build_owned_cards_progress_context_should_split_filtered_count_and_progress(
    monkeypatch,
) -> None:
    """顶部统计应让当前数量走筛选条件，高稀有度进度走固定全局。"""
    captured: dict[str, object] = {}

    def _fake_count_cards_by_scope(self, **kwargs):
        captured.update(kwargs)
        return 57

    monkeypatch.setattr(
        "ptcgp_auto_v2.web.services.owned_card_service.AccountCardRepository.count_cards_by_scope",
        _fake_count_cards_by_scope,
    )
    monkeypatch.setattr(
        "ptcgp_auto_v2.web.services.owned_card_service.AccountCardRepository.get_high_rarity_progress",
        lambda self: [{"rarity": "SR", "owned_count": 18, "total_count": 42}],
    )

    context = build_owned_cards_progress_context(
        account_id="rbksh2",
        rarity=["SR"],
        ownership_scope="all",
    )

    assert context == {
        "filtered_cards_count": 57,
        "rarity_progress": [{"rarity": "SR", "owned_count": 18, "total_count": 42}],
        "ownership_scope": "all",
    }
    assert captured["account_query"] == "rbksh2"
    assert captured["rarities"] == ["SR"]
    assert captured["ownership_scope"] == "all"
