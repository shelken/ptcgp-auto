# -*- coding: utf-8 -*-
"""Poke52LocalizationService 单元测试。"""

from __future__ import annotations

from ptcgp_auto_v2.services.metadata_sync.cache_store import TTLCacheStore
from ptcgp_auto_v2.services.metadata_sync.poke52_localization_service import (
    Poke52LocalizationService,
)


def test_build_localization_map_uses_cache_for_second_call() -> None:
    """同范围二次调用应命中缓存并减少远端请求次数。"""
    fake_client = _FakePoke52Client()
    service = Poke52LocalizationService(fake_client, TTLCacheStore(ttl_seconds=3600))

    first = service.build_localization_map(scope_level="set", scope_value="A1")
    second = service.build_localization_map(scope_level="set", scope_value="A1")

    assert first == second
    assert fake_client.calls["entry_links"] == 1
    assert fake_client.calls["series_wikitext"] == 1
    assert fake_client.calls["pack_wikitext"] == 1


def test_force_refresh_bypasses_cache() -> None:
    """强制刷新应绕过缓存重新抓取。"""
    fake_client = _FakePoke52Client()
    service = Poke52LocalizationService(fake_client, TTLCacheStore(ttl_seconds=3600))

    _ = service.build_localization_map(scope_level="set", scope_value="A1")
    _ = service.build_localization_map(
        scope_level="set",
        scope_value="A1",
        force_refresh=True,
    )

    assert fake_client.calls["entry_links"] == 2
    assert fake_client.calls["series_wikitext"] == 2
    assert fake_client.calls["pack_wikitext"] == 2


def test_card_scope_returns_only_target_card() -> None:
    """card 范围应只返回目标卡牌本地化。"""
    fake_client = _FakePoke52Client()
    service = Poke52LocalizationService(fake_client, TTLCacheStore(ttl_seconds=3600))

    result = service.build_localization_map(scope_level="card", scope_value="A1-001")
    cards = result["cards"]

    assert len(cards) == 1
    assert cards[0]["set_code"] == "A1"
    assert cards[0]["number"] == 1
    assert cards[0]["localized_name"] == "妙蛙種子"


class _FakePoke52Client:
    """52poke 客户端测试桩。"""

    def __init__(self) -> None:
        self.calls = {
            "entry_links": 0,
            "series_wikitext": 0,
            "pack_wikitext": 0,
        }

    def fetch_entry_links(self) -> list[str]:
        self.calls["entry_links"] += 1
        return ["A系列（TCGP）"]

    def fetch_series_wikitext(self, _title: str) -> str:
        self.calls["series_wikitext"] += 1
        return "* {{TCGP|最強的基因}}"

    def fetch_pack_wikitext(self, _title: str) -> str:
        self.calls["pack_wikitext"] += 1
        return """
|alt=A1
|setname=最強的基因
{{卡牌列表/entryp|001/286|{{C|妙蛙種子|草}}}}
{{卡牌列表/entryp|002/286|{{TCGP|妙蛙草}}}}
"""
