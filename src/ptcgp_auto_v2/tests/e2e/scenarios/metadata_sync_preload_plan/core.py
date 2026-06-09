# -*- coding: utf-8 -*-
"""metadata sync 预加载计划 service integration E2E 场景。"""

from __future__ import annotations

import io
from contextlib import redirect_stdout
from typing import Any

from sqlmodel import col, func, select

from ptcgp_auto_v2.db.engine import session_scope
from ptcgp_auto_v2.db.models import Card, CardPack, CardSet, Pack
from ptcgp_auto_v2.db.repositories.card_repository import CardRepository
from ptcgp_auto_v2.services.metadata_sync.flibustier_sync_service import (
    FlibustierSyncService,
)


def _remote_fixture() -> tuple[
    dict[str, list[dict[str, Any]]],
    list[dict[str, Any]],
    dict[tuple[str, int], dict[str, Any]],
]:
    cards_data = [
        {
            "set": "E2E",
            "number": 1,
            "name": "Noopmon",
            "rarity": "C",
            "image": "E2E_001.webp",
            "packs": ["Pack Alpha", "Pack Beta"],
            "element": "grass",
            "type": "pokemon",
            "stage": "basic",
            "health": 70,
            "weakness": "fire",
            "retreatCost": 1,
        },
        {
            "set": "E2E",
            "number": 2,
            "name": "Updatemon",
            "rarity": "U",
            "image": "E2E_002.webp",
            "packs": ["Pack Alpha", "Pack Beta"],
            "element": "water",
            "type": "pokemon",
            "stage": "stage1",
            "health": 90,
            "weakness": "lightning",
            "retreatCost": 2,
        },
        {
            "set": "E2E",
            "number": 3,
            "name": "Createmon",
            "rarity": "R",
            "image": "E2E_003.webp",
            "packs": ["Pack Beta", "Pack Alpha", "Pack Alpha"],
            "element": "fire",
            "type": "pokemon",
            "stage": "basic",
            "health": 60,
            "weakness": "water",
            "retreatCost": 1,
        },
    ]
    sets_data = {
        "E2E": [
            {
                "code": "E2E",
                "name": {"en": "E2E Metadata Set"},
                "count": len(cards_data),
                "releaseDate": None,
                "packs": ["Pack Alpha", "Pack Beta"],
            }
        ]
    }
    extra_map = {
        (str(card["set"]), int(card["number"])): card for card in cards_data
    }
    return sets_data, cards_data, extra_map


def _seed_existing_metadata() -> None:
    with session_scope() as session:
        session.add(
            CardSet(
                code="E2E",
                name="E2E Metadata Set",
                total_cards=3,
                label_data='{"en":"E2E Metadata Set"}',
            )
        )
        session.add(Pack(name="Pack Alpha", set_code="E2E", label_data='{"en":"Pack Alpha"}'))
        session.add(Pack(name="Pack Beta", set_code="E2E", label_data='{"en":"Pack Beta"}'))
        same_card = Card(
            set_code="E2E",
            number=1,
            name="Noopmon",
            rarity="C",
            image_url="E2E_001.webp",
            element="grass",
            type="pokemon",
            stage="basic",
            health=70,
            weakness="fire",
            retreat_cost=1,
        )
        changed_card = Card(
            set_code="E2E",
            number=2,
            name="Old Updatemon",
            rarity="U",
            image_url="E2E_002_old.webp",
            element="water",
            type="pokemon",
            stage="stage1",
            health=90,
            weakness="lightning",
            retreat_cost=2,
        )
        session.add(same_card)
        session.add(changed_card)
        session.flush()
        if same_card.id is None or changed_card.id is None:
            raise RuntimeError("seed card id is None")
        session.add(CardPack(card_id=same_card.id, pack_name="Pack Alpha"))
        session.add(CardPack(card_id=same_card.id, pack_name="Pack Beta"))
        session.add(CardPack(card_id=changed_card.id, pack_name="Pack Alpha"))


def _card_ops_by_number(plan: dict[str, Any]) -> dict[int, dict[str, Any]]:
    return {
        int(item["card"]["number"]): item
        for item in plan["operations"]["cards"]
    }


def _assert_plan_outcomes(plan: dict[str, Any]) -> None:
    card_ops = _card_ops_by_number(plan)
    assert set(card_ops) == {1, 2, 3}

    noop_equivalent = card_ops[1]
    assert noop_equivalent["op_type"] == "force"
    assert noop_equivalent["changed_values"] == [
        {"field": "__force__", "from": "same", "to": "same"}
    ]
    assert noop_equivalent["add_pack_names"] == []

    update_equivalent = card_ops[2]
    assert update_equivalent["op_type"] == "force"
    assert {item["field"] for item in update_equivalent["changed_values"]} == {
        "name",
        "image_url",
    }
    assert update_equivalent["add_pack_names"] == ["Pack Beta"]

    create_op = card_ops[3]
    assert create_op["op_type"] == "create"
    assert create_op["needs_upsert"] is True
    assert create_op["add_pack_names"] == ["Pack Alpha", "Pack Beta"]

    assert plan["summary"] == {
        "upsert_sets": 1,
        "upsert_packs": 2,
        "card_updates": 3,
        "card_pack_links_to_add": 3,
        "card_pack_links_to_remove": 0,
    }


def _assert_db_state() -> None:
    with session_scope() as session:
        cards = {
            int(card.number): card
            for card in session.exec(
                select(Card).where(Card.set_code == "E2E").order_by(Card.number)
            ).all()
        }
        assert set(cards) == {1, 2, 3}
        assert cards[1].name == "Noopmon"
        assert cards[2].name == "Updatemon"
        assert cards[2].image_url == "E2E_002.webp"
        assert cards[3].name == "Createmon"

        rows = session.exec(
            select(Card.number, CardPack.pack_name)
            .join(CardPack, col(Card.id) == col(CardPack.card_id))
            .where(Card.set_code == "E2E")
            .order_by(Card.number, CardPack.pack_name)
        ).all()
        assert rows == [
            (1, "Pack Alpha"),
            (1, "Pack Beta"),
            (2, "Pack Alpha"),
            (2, "Pack Beta"),
            (3, "Pack Alpha"),
            (3, "Pack Beta"),
        ]

        duplicate_count = session.exec(
            select(func.count())
            .select_from(CardPack)
            .group_by(CardPack.card_id, CardPack.pack_name)
            .having(func.count() > 1)
        ).all()
        assert duplicate_count == []


def run(ctx):
    """用真实同步服务验证预加载计划与 card_packs 关联落库。"""
    ctx.log(ctx.config.description)
    ctx.log("service integration E2E：不启动 scheduler/device，仅断言隔离 DB 状态")
    _seed_existing_metadata()
    sets_data, cards_data, extra_map = _remote_fixture()

    stdout = io.StringIO()
    with session_scope() as session, redirect_stdout(stdout):
        service = FlibustierSyncService(CardRepository(session))
        plan = service.build_plan(
            mode="force",
            scope_level="all",
            scope_value=None,
            sets_data=sets_data,
            cards_data=cards_data,
            extra_map=extra_map,
        )
        _assert_plan_outcomes(plan)
        result = service.execute_plan(plan["operations"])

    assert result == {
        "upsert_sets": 1,
        "upsert_packs": 2,
        "card_updates": 3,
        "card_pack_links_to_add": 3,
        "card_pack_links_to_remove": 0,
    }
    assert "[ptcgp-assets]" not in stdout.getvalue()
    _assert_db_state()
