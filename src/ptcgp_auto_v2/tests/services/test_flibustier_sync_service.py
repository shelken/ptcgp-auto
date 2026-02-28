# -*- coding: utf-8 -*-
"""FlibustierSyncService 单元测试。"""

from __future__ import annotations

import json

from ptcgp_auto_v2.db.models import Card, CardSet, Pack
from ptcgp_auto_v2.db.repositories import CardRepository
from ptcgp_auto_v2.services.metadata_sync.flibustier_sync_service import (
    FlibustierSyncService,
)


def _seed_local_base(repo: CardRepository) -> None:
    """准备本地基础数据。"""
    repo.upsert_set(
        CardSet(
            code="A1",
            name="Old Set",
            release_date="2024-01-01",
            total_cards=10,
            label_data=json.dumps({"en": "Old Set"}, ensure_ascii=False),
        )
    )
    repo.upsert_pack_safe(
        Pack(
            name="PackOld",
            set_code="A1",
            label_data=json.dumps({"en": "PackOld"}, ensure_ascii=False),
        )
    )
    old_card = repo.upsert_card(
        Card(
            set_code="A1",
            number=1,
            name="CardOld",
            rarity="C",
            image_url="old.webp",
            data=json.dumps(
                {
                    "set": "A1",
                    "number": "001",
                    "name": "CardOld",
                    "rarity": "C",
                    "packs": ["PackOld"],
                },
                ensure_ascii=False,
            ),
        )
    )
    assert old_card.id is not None
    repo.add_card_pack(old_card.id, "PackOld")


def _remote_payload() -> tuple[dict, list, dict]:
    """构造远端元数据载荷。"""
    sets_data = {
        "main": [
            {
                "code": "A1",
                "name": {"en": "New Set"},
                "releaseDate": "2024-01-01",
                "count": 10,
            }
        ]
    }
    cards_data = [
        {
            "set": "A1",
            "number": "1",
            "name": "CardNew",
            "rarity": "C",
            "image": "new.webp",
            "packs": ["PackNew"],
        }
    ]
    extra_map: dict = {}
    return sets_data, cards_data, extra_map


def test_supplement_mode_only_adds_missing_entities_and_links() -> None:
    """supplement 模式仅补充新增记录与新增关联，不覆盖已有字段。"""
    repo = CardRepository()
    _seed_local_base(repo)
    sets_data, cards_data, extra_map = _remote_payload()

    service = FlibustierSyncService(repo)
    plan = service.build_plan(
        mode="supplement",
        scope_level="all",
        scope_value=None,
        sets_data=sets_data,
        cards_data=cards_data,
        extra_map=extra_map,
    )

    assert plan["summary"]["upsert_sets"] == 0
    assert plan["summary"]["upsert_packs"] == 1
    assert plan["summary"]["card_updates"] == 0
    assert plan["summary"]["card_pack_links_to_add"] == 1

    service.execute_plan(plan["operations"])

    card = repo.get_card_by_set_and_number("A1", 1)
    assert card is not None
    assert card.name == "CardOld"

    card_set = repo.get_set_by_code("A1")
    assert card_set is not None
    assert card_set.name == "Old Set"

    card_pack_names = sorted(repo.get_card_pack_names(card.id or 0))
    assert card_pack_names == ["PackNew", "PackOld"]


def test_force_mode_overwrites_existing_without_deleting_links() -> None:
    """force 模式覆盖已有字段，但不删除本地旧关联。"""
    repo = CardRepository()
    _seed_local_base(repo)
    sets_data, cards_data, extra_map = _remote_payload()

    service = FlibustierSyncService(repo)
    plan = service.build_plan(
        mode="force",
        scope_level="all",
        scope_value=None,
        sets_data=sets_data,
        cards_data=cards_data,
        extra_map=extra_map,
    )

    assert plan["summary"]["upsert_sets"] == 1
    assert plan["summary"]["card_updates"] == 1
    assert plan["summary"]["card_pack_links_to_remove"] == 0

    service.execute_plan(plan["operations"])

    card = repo.get_card_by_set_and_number("A1", 1)
    assert card is not None
    assert card.name == "CardNew"

    card_set = repo.get_set_by_code("A1")
    assert card_set is not None
    assert card_set.name == "New Set"

    card_pack_names = sorted(repo.get_card_pack_names(card.id or 0))
    assert card_pack_names == ["PackNew", "PackOld"]


def test_set_scope_only_returns_target_set_operations() -> None:
    """set 范围应仅保留目标系列相关操作。"""
    repo = CardRepository()
    sets_data = {
        "main": [
            {
                "code": "A1",
                "name": {"en": "Set A1"},
                "releaseDate": "2024-01-01",
                "count": 1,
            },
            {
                "code": "A2",
                "name": {"en": "Set A2"},
                "releaseDate": "2024-01-01",
                "count": 1,
            },
        ]
    }
    cards_data = [
        {
            "set": "A1",
            "number": "1",
            "name": "A1-Card",
            "rarity": "C",
            "image": "a1.webp",
            "packs": ["A1Pack"],
        },
        {
            "set": "A2",
            "number": "1",
            "name": "A2-Card",
            "rarity": "C",
            "image": "a2.webp",
            "packs": ["A2Pack"],
        },
    ]

    service = FlibustierSyncService(repo)
    plan = service.build_plan(
        mode="force",
        scope_level="set",
        scope_value="A2",
        sets_data=sets_data,
        cards_data=cards_data,
        extra_map={},
    )

    set_codes = [item["code"] for item in plan["operations"]["sets"]]
    card_set_codes = [item["card"]["set_code"] for item in plan["operations"]["cards"]]
    pack_set_codes = [item["set_code"] for item in plan["operations"]["packs"]]

    assert set_codes == ["A2"]
    assert card_set_codes == ["A2"]
    assert pack_set_codes == ["A2"]
