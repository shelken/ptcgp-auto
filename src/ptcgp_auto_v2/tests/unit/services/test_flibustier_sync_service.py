# -*- coding: utf-8 -*-

from __future__ import annotations

from types import SimpleNamespace
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
    def get_set_by_code(self, code: str):
        return None

    def get_card_by_set_and_number(self, set_code: str, number: int):
        return None

    def get_pack_by_name(self, name: str):
        return None


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


def test_build_plan_uses_sets_packs_for_pack_operations():
    sets_data = {
        "Other": [
            {
                "code": "A1a",
                "name": {"en": "Mythical Island"},
                "count": 1,
                "releaseDate": None,
                "packs": ["Mythical Island"],
            }
        ]
    }
    cards_data = [
        {
            "set": "A1a",
            "number": 1,
            "name": "Mew",
            "rarity": "◊◊◊",
            "image": "A1a_001.webp",
            "packs": ["Mythical Island", "Deluxe Pack ex"],
            "type": "pokemon",
            "element": "psychic",
            "stage": "basic",
            "health": 60,
            "retreatCost": 1,
            "weakness": "darkness",
            "evolvesFrom": None,
        }
    ]

    plan = FlibustierSyncService(FakeRepo()).build_plan(  # type: ignore[arg-type]
        mode="supplement",
        scope_level="all",
        scope_value=None,
        sets_data=sets_data,
        cards_data=cards_data,
        extra_map={("A1a", 1): cards_data[0]},
    )

    pack_names = {item["name"] for item in plan["operations"]["packs"]}
    assert pack_names == {"Mythical Island"}


def test_build_plan_ignores_card_pack_links_outside_pack_universe():
    sets_data = {
        "Other": [
            {
                "code": "A1a",
                "name": {"en": "Mythical Island"},
                "count": 1,
                "releaseDate": None,
                "packs": ["Mythical Island"],
            }
        ]
    }
    cards_data = [
        {
            "set": "A1a",
            "number": 1,
            "name": "Mew",
            "rarity": "◊◊◊",
            "image": "A1a_001.webp",
            "packs": ["Mythical Island", "Missing Pack"],
            "type": "pokemon",
            "element": "psychic",
            "stage": "basic",
            "health": 60,
            "retreatCost": 1,
            "weakness": "darkness",
            "evolvesFrom": None,
        }
    ]

    plan = FlibustierSyncService(FakeRepo()).build_plan(  # type: ignore[arg-type]
        mode="supplement",
        scope_level="all",
        scope_value=None,
        sets_data=sets_data,
        cards_data=cards_data,
        extra_map={("A1a", 1): cards_data[0]},
    )

    card_ops = plan["operations"]["cards"]
    assert len(card_ops) == 1
    assert card_ops[0]["add_pack_names"] == ["Mythical Island"]


def test_build_plan_set_scope_keeps_cross_set_card_pack_link_from_full_pack_universe():
    sets_data = {
        "A": [
            {
                "code": "A1",
                "name": {"en": "Genetic Apex"},
                "count": 1,
                "releaseDate": None,
                "packs": ["Mewtwo"],
            },
            {
                "code": "A4b",
                "name": {"en": "Deluxe Pack ex"},
                "count": 1,
                "releaseDate": None,
                "packs": ["Deluxe Pack ex"],
            },
        ]
    }
    cards_data = [
        {
            "set": "A1",
            "number": 1,
            "name": "Bulbasaur",
            "rarity": "C",
            "image": "A1_001.webp",
            "packs": ["Mewtwo", "Deluxe Pack ex"],
        }
    ]

    plan = FlibustierSyncService(FakeRepo()).build_plan(  # type: ignore[arg-type]
        mode="supplement",
        scope_level="set",
        scope_value="A1",
        sets_data=sets_data,
        cards_data=cards_data,
        extra_map={("A1", 1): cards_data[0]},
    )

    assert plan["operations"]["packs"] == [
        {
            "name": "Mewtwo",
            "set_code": "A1",
            "label_data": '{"en": "Mewtwo"}',
            "op_type": "create",
            "changed_values": [
                {"field": "name", "from": "", "to": "Mewtwo"},
                {"field": "set_code", "from": "", "to": "A1"},
            ],
        }
    ]
    assert plan["operations"]["cards"][0]["add_pack_names"] == [
        "Deluxe Pack ex",
        "Mewtwo",
    ]


def test_build_plan_card_scope_keeps_cross_set_card_pack_link_from_full_pack_universe():
    sets_data = {
        "A": [
            {
                "code": "A1",
                "name": {"en": "Genetic Apex"},
                "count": 1,
                "releaseDate": None,
                "packs": ["Mewtwo"],
            },
            {
                "code": "A4b",
                "name": {"en": "Deluxe Pack ex"},
                "count": 1,
                "releaseDate": None,
                "packs": ["Deluxe Pack ex"],
            },
        ]
    }
    cards_data = [
        {
            "set": "A1",
            "number": 1,
            "name": "Bulbasaur",
            "rarity": "C",
            "image": "A1_001.webp",
            "packs": ["Mewtwo", "Deluxe Pack ex"],
        }
    ]

    plan = FlibustierSyncService(FakeRepo()).build_plan(  # type: ignore[arg-type]
        mode="supplement",
        scope_level="card",
        scope_value="A1-001",
        sets_data=sets_data,
        cards_data=cards_data,
        extra_map={("A1", 1): cards_data[0]},
    )

    assert plan["operations"]["packs"] == [
        {
            "name": "Mewtwo",
            "set_code": "A1",
            "label_data": '{"en": "Mewtwo"}',
            "op_type": "create",
            "changed_values": [
                {"field": "name", "from": "", "to": "Mewtwo"},
                {"field": "set_code", "from": "", "to": "A1"},
            ],
        }
    ]
    assert plan["operations"]["cards"][0]["add_pack_names"] == [
        "Deluxe Pack ex",
        "Mewtwo",
    ]


def test_build_plan_pack_scope_uses_set_from_pack_universe():
    sets_data = {
        "A": [
            {
                "code": "A1",
                "name": {"en": "Genetic Apex"},
                "count": 1,
                "releaseDate": None,
                "packs": ["Mewtwo"],
            },
            {
                "code": "A4b",
                "name": {"en": "Deluxe Pack ex"},
                "count": 1,
                "releaseDate": None,
                "packs": ["Deluxe Pack ex"],
            },
        ]
    }
    cards_data = [
        {
            "set": "A1",
            "number": 1,
            "name": "Bulbasaur",
            "rarity": "C",
            "image": "A1_001.webp",
            "packs": ["Deluxe Pack ex"],
        }
    ]

    plan = FlibustierSyncService(FakeRepo()).build_plan(  # type: ignore[arg-type]
        mode="supplement",
        scope_level="pack",
        scope_value="Deluxe Pack ex",
        sets_data=sets_data,
        cards_data=cards_data,
        extra_map={("A1", 1): cards_data[0]},
    )

    assert plan["operations"]["packs"] == [
        {
            "name": "Deluxe Pack ex",
            "set_code": "A4b",
            "label_data": '{"en": "Deluxe Pack ex"}',
            "op_type": "create",
            "changed_values": [
                {"field": "name", "from": "", "to": "Deluxe Pack ex"},
                {"field": "set_code", "from": "", "to": "A4b"},
            ],
        }
    ]


def test_supplement_existing_card_link_does_not_report_field_updates():
    class ExistingCardRepo(FakeRepo):
        def get_card_by_set_and_number(self, set_code: str, number: int):
            return SimpleNamespace(
                id=10,
                name="Old Mew",
                rarity="◊◊◊",
                image_url="A1a_001.webp",
                element="psychic",
                type="pokemon",
                stage="basic",
                health=60,
                weakness="darkness",
                retreat_cost=1,
            )

        def get_card_pack_names(self, card_id: int) -> list[str]:
            return []

    sets_data = {
        "Other": [
            {
                "code": "A1a",
                "name": {"en": "Mythical Island"},
                "count": 1,
                "releaseDate": None,
                "packs": ["Mythical Island"],
            }
        ]
    }
    cards_data = [
        {
            "set": "A1a",
            "number": 1,
            "name": "Mew",
            "rarity": "◊◊◊",
            "image": "A1a_001.webp",
            "packs": ["Mythical Island", "Missing Pack"],
            "type": "pokemon",
            "element": "psychic",
            "stage": "basic",
            "health": 60,
            "retreatCost": 1,
            "weakness": "darkness",
        }
    ]

    plan = FlibustierSyncService(ExistingCardRepo()).build_plan(  # type: ignore[arg-type]
        mode="supplement",
        scope_level="all",
        scope_value=None,
        sets_data=sets_data,
        cards_data=cards_data,
        extra_map={("A1a", 1): cards_data[0]},
    )

    card_ops = plan["operations"]["cards"]
    assert len(card_ops) == 1
    assert card_ops[0]["op_type"] == "link"
    assert card_ops[0]["needs_upsert"] is False
    assert card_ops[0]["add_pack_names"] == ["Mythical Island"]
    assert card_ops[0]["changed_fields"] == []
    assert card_ops[0]["changed_values"] == []
