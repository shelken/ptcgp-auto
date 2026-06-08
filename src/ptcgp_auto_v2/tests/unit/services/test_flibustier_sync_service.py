# -*- coding: utf-8 -*-

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

from sqlmodel import Session, SQLModel, create_engine, select

from ptcgp_auto_v2.db.models import Card, CardPack, CardSet, Pack
from ptcgp_auto_v2.db.repositories.card_repository import CardRepository
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

    def get_cards_by_set_and_numbers(self, keys):
        cards = {}
        for set_code, number in keys:
            card = self.get_card_by_set_and_number(set_code, number)
            if card is not None:
                cards[(set_code, number)] = card
        return cards

    def get_card_pack_names(self, card_id: int) -> list[str]:
        return []

    def get_card_pack_names_map(self, card_ids):
        return {card_id: self.get_card_pack_names(card_id) for card_id in card_ids}

    def get_pack_by_name(self, name: str):
        return None


class ExistingPackMissingAssetsRepo(FakeRepo):
    def get_pack_by_name(self, name: str):
        return SimpleNamespace(
            name=name,
            set_code="B1",
            label_data='{"en":"Mega Altaria"}',
            sku_id=None,
            image_url=None,
        )


class ExistingSetRepo(FakeRepo):
    def get_set_by_code(self, code: str):
        return SimpleNamespace(
            code=code,
            name="Mega Rising",
            release_date="2025-10-30",
            total_cards=331,
            label_data='{"en":"Mega Rising"}',
        )


class CountingExistingCardRepo(FakeRepo):
    def __init__(self):
        self.get_card_by_set_and_number_calls = 0
        self.get_card_pack_names_calls = 0
        self.get_cards_by_set_and_numbers_calls = 0
        self.get_card_pack_names_map_calls = 0
        self.cards = {
            ("A1", 1): SimpleNamespace(
                id=101,
                name="Bulbasaur",
                rarity="C",
                image_url="A1_001.webp",
                element="grass",
                type="pokemon",
                stage="basic",
                health=70,
                weakness="Fire",
                retreat_cost=1,
            ),
            ("A1", 2): SimpleNamespace(
                id=102,
                name="Old Ivysaur",
                rarity="U",
                image_url="A1_002_old.webp",
                element="grass",
                type="pokemon",
                stage="stage1",
                health=90,
                weakness="Fire",
                retreat_cost=2,
            ),
        }
        self.pack_names = {
            101: ["Mewtwo"],
            102: ["Mewtwo"],
        }

    def get_card_by_set_and_number(self, set_code: str, number: int):
        self.get_card_by_set_and_number_calls += 1
        return self.cards.get((set_code, number))

    def get_cards_by_set_and_numbers(self, keys):
        self.get_cards_by_set_and_numbers_calls += 1
        key_set = set(keys)
        return {key: card for key, card in self.cards.items() if key in key_set}

    def get_card_pack_names(self, card_id: int) -> list[str]:
        self.get_card_pack_names_calls += 1
        return self.pack_names.get(card_id, [])

    def get_card_pack_names_map(self, card_ids):
        self.get_card_pack_names_map_calls += 1
        id_set = set(card_ids)
        return {card_id: names for card_id, names in self.pack_names.items() if card_id in id_set}


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


def test_build_plan_preloads_existing_cards_and_card_packs():
    sets_data = {
        "A": [
            {
                "code": "A1",
                "name": {"en": "Genetic Apex"},
                "count": 2,
                "releaseDate": None,
                "packs": ["Mewtwo", "Charizard"],
            }
        ]
    }
    cards_data = [
        {
            "set": "A1",
            "number": 1,
            "name": "Bulbasaur",
            "rarity": "C",
            "image": "A1_001.webp",
            "packs": ["Mewtwo", "Charizard"],
            "element": "grass",
            "type": "pokemon",
            "stage": "basic",
            "health": 70,
            "weakness": "Fire",
            "retreatCost": 1,
        },
        {
            "set": "A1",
            "number": 2,
            "name": "Ivysaur",
            "rarity": "U",
            "image": "A1_002.webp",
            "packs": ["Mewtwo"],
            "element": "grass",
            "type": "pokemon",
            "stage": "stage1",
            "health": 90,
            "weakness": "Fire",
            "retreatCost": 2,
        },
    ]
    repo = CountingExistingCardRepo()

    plan = FlibustierSyncService(repo).build_plan(  # type: ignore[arg-type]
        mode="force",
        scope_level="all",
        scope_value=None,
        sets_data=sets_data,
        cards_data=cards_data,
        extra_map={("A1", 1): cards_data[0], ("A1", 2): cards_data[1]},
    )

    assert repo.get_cards_by_set_and_numbers_calls == 1
    assert repo.get_card_pack_names_map_calls == 1
    assert repo.get_card_by_set_and_number_calls == 0
    assert repo.get_card_pack_names_calls == 0
    card_ops = plan["operations"]["cards"]
    assert len(card_ops) == 2
    assert card_ops[0]["op_type"] == "force"
    assert card_ops[0]["add_pack_names"] == ["Charizard"]
    assert card_ops[0]["changed_values"] == [
        {"field": "__force__", "from": "same", "to": "same"}
    ]
    assert card_ops[1]["op_type"] == "force"
    assert card_ops[1]["add_pack_names"] == []
    assert {item["field"] for item in card_ops[1]["changed_values"]} == {"name", "image_url"}


def test_build_plan_does_not_print_ptcgp_assets_debug_output(capsys):
    sets_data = {
        "B": [
            {
                "code": "B1",
                "name": {"en": "Mega Rising"},
                "count": 331,
                "releaseDate": None,
                "packs": ["Mega Blaziken"],
            }
        ]
    }

    FlibustierSyncService(ExistingSetRepo()).build_plan(  # type: ignore[arg-type]
        mode="supplement",
        scope_level="all",
        scope_value=None,
        sets_data=sets_data,
        cards_data=[],
        extra_map={},
    )

    assert "[ptcgp-assets]" not in capsys.readouterr().out


def test_card_repository_batch_reads_existing_cards_and_pack_names(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'metadata_batch.db'}")
    SQLModel.metadata.create_all(engine)

    with Session(engine) as session:
        session.add(CardSet(code="A1", name="Genetic Apex", total_cards=2))
        session.add(Pack(name="Mewtwo", set_code="A1"))
        card = Card(
            set_code="A1",
            number=1,
            name="Bulbasaur",
            rarity="C",
            image_url="A1_001.webp",
        )
        session.add(card)
        session.commit()
        session.refresh(card)
        assert card.id is not None
        card_id = card.id
        session.add(CardPack(card_id=card_id, pack_name="Mewtwo"))
        session.commit()

        repo = CardRepository(session)
        cards = repo.get_cards_by_set_and_numbers([("A1", 1), ("A1", 999)])
        pack_names = repo.get_card_pack_names_map([card_id, 999])
        assert repo.get_cards_by_set_and_numbers([]) == {}
        assert repo.get_card_pack_names_map([]) == {}

    assert set(cards) == {("A1", 1)}
    assert cards[("A1", 1)].name == "Bulbasaur"
    assert pack_names == {card_id: ["Mewtwo"], 999: []}


def test_build_plan_preserves_existing_release_date_when_remote_release_date_is_null():
    sets_data = {
        "B": [
            {
                "code": "B1",
                "name": {"en": "Mega Rising"},
                "count": 331,
                "releaseDate": None,
                "packs": ["Mega Blaziken"],
            }
        ]
    }

    plan = FlibustierSyncService(ExistingSetRepo()).build_plan(  # type: ignore[arg-type]
        mode="force",
        scope_level="all",
        scope_value=None,
        sets_data=sets_data,
        cards_data=[],
        extra_map={},
    )

    [set_op] = plan["operations"]["sets"]
    assert set_op["release_date"] == "2025-10-30"
    assert "release_date" not in {item["field"] for item in set_op["changed_values"]}


def test_object_pack_entry_generates_sku_id_and_image_url():
    sets_data = {
        "B": [
            {
                "code": "B1",
                "name": {"en": "Mega Rising"},
                "count": 1,
                "releaseDate": None,
                "packs": [{"name": "Mega Altaria", "skuId": "B1_3"}],
            }
        ]
    }

    plan = FlibustierSyncService(FakeRepo()).build_plan(  # type: ignore[arg-type]
        mode="supplement",
        scope_level="all",
        scope_value=None,
        sets_data=sets_data,
        cards_data=[],
        extra_map={},
    )

    [pack_op] = plan["operations"]["packs"]
    assert pack_op["name"] == "Mega Altaria"
    assert pack_op["set_code"] == "B1"
    assert pack_op["sku_id"] == "B1_3"
    assert pack_op["image_url"] == "https://raw.githubusercontent.com/shelken/ptcgp-assets/main/images/en-US/packs/B1_3.webp"


def test_string_pack_entry_stays_compatible_without_asset_fields():
    sets_data = {
        "A": [
            {
                "code": "A1a",
                "name": {"en": "Mythical Island"},
                "count": 1,
                "releaseDate": None,
                "packs": ["Mythical Island"],
            }
        ]
    }

    plan = FlibustierSyncService(FakeRepo()).build_plan(  # type: ignore[arg-type]
        mode="supplement",
        scope_level="all",
        scope_value=None,
        sets_data=sets_data,
        cards_data=[],
        extra_map={},
    )

    [pack_op] = plan["operations"]["packs"]
    assert pack_op["name"] == "Mythical Island"
    assert pack_op["sku_id"] is None
    assert pack_op["image_url"] is None


def test_supplement_existing_pack_fills_missing_asset_fields():
    sets_data = {
        "B": [
            {
                "code": "B1",
                "name": {"en": "Mega Rising"},
                "count": 1,
                "releaseDate": None,
                "packs": [{"name": "Mega Altaria", "skuId": "B1_3"}],
            }
        ]
    }

    plan = FlibustierSyncService(ExistingPackMissingAssetsRepo()).build_plan(  # type: ignore[arg-type]
        mode="supplement",
        scope_level="all",
        scope_value=None,
        sets_data=sets_data,
        cards_data=[],
        extra_map={},
    )

    [pack_op] = plan["operations"]["packs"]
    assert pack_op["op_type"] == "update"
    assert {item["field"] for item in pack_op["changed_values"]} == {"sku_id", "image_url"}


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

    assert [(item["name"], item["set_code"]) for item in plan["operations"]["packs"]] == [
        ("Mewtwo", "A1"),
        ("Deluxe Pack ex", "A4b"),
    ]
    assert plan["operations"]["cards"][0]["add_pack_names"] == [
        "Deluxe Pack ex",
        "Mewtwo",
    ]


def test_execute_set_scope_creates_packs_for_cross_set_card_pack_links(tmp_path):
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
    engine = create_engine(f"sqlite:///{tmp_path / 'metadata.db'}")
    SQLModel.metadata.create_all(engine)

    with Session(engine) as session:
        repo = CardRepository(session)
        service = FlibustierSyncService(repo)
        plan = service.build_plan(
            mode="supplement",
            scope_level="set",
            scope_value="A1",
            sets_data=sets_data,
            cards_data=cards_data,
            extra_map={("A1", 1): cards_data[0]},
        )
        service.execute_plan(plan["operations"])

        pack_names = set(session.exec(select(Pack.name)).all())
        linked_pack_names = set(session.exec(select(CardPack.pack_name)).all())

    assert linked_pack_names == {"Deluxe Pack ex", "Mewtwo"}
    assert linked_pack_names <= pack_names


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

    assert [(item["name"], item["set_code"]) for item in plan["operations"]["packs"]] == [
        ("Mewtwo", "A1"),
        ("Deluxe Pack ex", "A4b"),
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
            "sku_id": None,
            "image_url": None,
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
