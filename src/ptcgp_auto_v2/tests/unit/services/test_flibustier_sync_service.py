# -*- coding: utf-8 -*-

from __future__ import annotations

from typing import Any

from ptcgp_auto_v2.services.metadata_sync import flibustier_sync_service as service_module
from ptcgp_auto_v2.services.metadata_sync.flibustier_sync_service import FlibustierSyncService


class FakeResponse:
    def __init__(self, payload: Any):
        self._payload = payload

    def raise_for_status(self) -> None:
        pass

    def json(self) -> Any:
        return self._payload


class FakeRepo:
    pass


def test_fetch_remote_metadata_uses_cards_extra_as_card_source(monkeypatch):
    requested_urls: list[str] = []
    sets_payload = {"A": [{"code": "A1", "name": {"en": "Genetic Apex"}, "count": 1, "packs": ["Mewtwo"]}]}
    extra_payload = [
        {
            "set": "A1",
            "number": 1,
            "name": "Bulbasaur",
            "rarity": "C",
            "image": "bulbasaur.webp",
            "packs": ["Mewtwo", "Deluxe Pack ex"],
            "element": "grass",
            "type": "pokemon",
            "stage": "basic",
            "health": 70,
            "weakness": "Fire",
            "retreatCost": 1,
        }
    ]

    def fake_get(url: str, timeout: int) -> FakeResponse:
        requested_urls.append(url)
        if url == service_module.SETS_URL:
            return FakeResponse(sets_payload)
        if url == service_module.CARDS_EXTRA_URL:
            return FakeResponse(extra_payload)
        raise AssertionError(f"不应请求旧 cards.json: {url}")

    monkeypatch.setattr(service_module.requests, "get", fake_get)

    sets_data, cards_data, extra_map = FlibustierSyncService(FakeRepo()).fetch_remote_metadata(force_refresh=True)  # type: ignore[arg-type]

    assert requested_urls == [service_module.SETS_URL, service_module.CARDS_EXTRA_URL]
    assert sets_data == sets_payload
    assert cards_data == extra_payload
    assert extra_map == {("A1", 1): extra_payload[0]}
