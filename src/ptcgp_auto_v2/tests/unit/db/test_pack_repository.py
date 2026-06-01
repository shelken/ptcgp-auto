# -*- coding: utf-8 -*-
"""Pack repository 行为测试。"""

from __future__ import annotations

from pathlib import Path

from sqlmodel import Session, SQLModel, create_engine

from ptcgp_auto_v2.db.models import Card, CardPack, CardSet, Pack
from ptcgp_auto_v2.db.repositories.card_repository import CardRepository


def test_pack_name_alignment_migration_uses_localtime_timestamps():
    migration_path = (
        Path(__file__).resolve().parents[5]
        / "scripts/migrations/2026_05_30_pack_name_alignment.sql"
    )
    sql = migration_path.read_text(encoding="utf-8")

    assert "CURRENT_TIMESTAMP" not in sql
    assert sql.count("datetime('now', 'localtime')") == 3


def test_get_packs_by_set_reads_packs_table_not_card_links(tmp_path):
    db_path = tmp_path / "packs.db"
    engine = create_engine(f"sqlite:///{db_path}")
    SQLModel.metadata.create_all(engine)

    with Session(engine) as session:
        session.add(CardSet(code="A1", name="Genetic Apex", total_cards=1))
        session.add(CardSet(code="A4b", name="Deluxe Pack ex", total_cards=1))
        session.add(Pack(name="Mewtwo", set_code="A1", label_data='{"en":"Mewtwo"}'))
        session.add(
            Pack(
                name="Deluxe Pack ex",
                set_code="A4b",
                label_data='{"en":"Deluxe Pack ex"}',
            )
        )
        session.add(
            Card(set_code="A1", number=1, name="Bulbasaur", rarity="C", image_url="1.webp")
        )
        session.flush()
        card_id = session.exec(Card.__table__.select()).first().id
        session.add(CardPack(card_id=card_id, pack_name="Deluxe Pack ex"))
        session.commit()

    with Session(engine) as session:
        result = CardRepository(session).get_packs_by_set("A1")

    assert result == {"A1": {"name": "Genetic Apex", "boosters": ["Mewtwo"]}}
