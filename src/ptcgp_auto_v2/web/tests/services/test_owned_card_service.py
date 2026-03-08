# -*- coding: utf-8 -*-

"""owned_card_service 列表上下文测试。"""

from ptcgp_auto_v2.web.services.owned_card_service import build_owned_cards_list_context


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

    context = build_owned_cards_list_context(
        session=None,
        page=0,
        page_size=10,
        account_id="rbksh2",
    )

    assert context["items"] == []
    assert captured["account_query"] == "rbksh2"
