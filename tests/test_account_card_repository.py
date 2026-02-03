# -*- coding: utf-8 -*-

from datetime import datetime

from sqlmodel import SQLModel, Session, create_engine, select

from ptcgp_auto_v2.db import engine as db_engine
from ptcgp_auto_v2.db.repositories import AccountCardRepository
from ptcgp_auto_v2.db.models import Account, AccountCard, Card, CardPack, CardSet


def test_account_card_upsert():
    db_engine._engine = create_engine("sqlite:///:memory:")
    SQLModel.metadata.create_all(db_engine._engine)

    repo = AccountCardRepository()
    repo.upsert(account_id=1, card_id=10, count=1)
    repo.upsert(account_id=1, card_id=10, count=1)

    row = repo.get(account_id=1, card_id=10)
    assert row is not None
    assert row.count == 1


def _seed_owned_cards_data():
    with Session(db_engine._engine) as session:
        session.add_all(
            [
                CardSet(code="A1", name="Alpha"),
                CardSet(code="B1", name="Beta"),
            ]
        )
        session.add_all(
            [
                Card(
                    id=1,
                    set_code="A1",
                    number=10,
                    name="Card SR",
                    rarity="SR",
                    image_url="",
                    type="pokemon",
                    element="fire",
                ),
                Card(
                    id=2,
                    set_code="A1",
                    number=5,
                    name="Card R",
                    rarity="R",
                    image_url="",
                    type="pokemon",
                    element="water",
                ),
                Card(
                    id=3,
                    set_code="B1",
                    number=1,
                    name="Card SR 2",
                    rarity="SR",
                    image_url="",
                    type="trainer",
                    element=None,
                ),
            ]
        )
        session.add_all(
            [
                Account(id=1, game_id="G1", friend_id="F1", nickname="A1"),
                Account(id=2, game_id="G2", friend_id="F2", nickname="A2"),
            ]
        )
        session.add_all(
            [
                AccountCard(account_id=1, card_id=1, count=2),
                AccountCard(account_id=2, card_id=1, count=1),
                AccountCard(account_id=1, card_id=2, count=1),
                AccountCard(account_id=1, card_id=3, count=1),
            ]
        )
        session.add_all(
            [
                CardPack(card_id=1, pack_name="Mewtwo"),
                CardPack(card_id=2, pack_name="Pikachu"),
                CardPack(card_id=3, pack_name="Mewtwo"),
            ]
        )
        session.commit()


def test_list_owned_cards_sorting_and_filters():
    db_engine._engine = create_engine("sqlite:///:memory:")
    SQLModel.metadata.create_all(db_engine._engine)
    _seed_owned_cards_data()

    repo = AccountCardRepository()
    items = repo.list_owned_cards(page=0, page_size=10)
    assert [item["card"].id for item in items] == [1, 3, 2]

    items = repo.list_owned_cards(page=0, page_size=10, rarities=["SR"])
    assert {item["card"].id for item in items} == {1, 3}

    items = repo.list_owned_cards(page=0, page_size=10, card_types=["trainer"])
    assert [item["card"].id for item in items] == [3]

    items = repo.list_owned_cards(page=0, page_size=10, set_codes=["A1"])
    assert {item["card"].id for item in items} == {1, 2}

    items = repo.list_owned_cards(page=0, page_size=10, pack_names=["Mewtwo"])
    assert {item["card"].id for item in items} == {1, 3}

    items = repo.list_owned_cards(page=0, page_size=10, elements=["fire"])
    assert [item["card"].id for item in items] == [1]


def test_list_owned_cards_element_filter_case_insensitive():
    db_engine._engine = create_engine("sqlite:///:memory:")
    SQLModel.metadata.create_all(db_engine._engine)
    _seed_owned_cards_data()

    with Session(db_engine._engine) as session:
        card = session.get(Card, 1)
        assert card is not None
        card.element = "Fire"
        session.add(card)
        session.commit()

    repo = AccountCardRepository()
    items = repo.list_owned_cards(page=0, page_size=10, elements=["fire"])
    assert [item["card"].id for item in items] == [1]


def test_get_owned_card_accounts():
    db_engine._engine = create_engine("sqlite:///:memory:")
    SQLModel.metadata.create_all(db_engine._engine)
    _seed_owned_cards_data()

    repo = AccountCardRepository()
    result = repo.get_owned_card_accounts(card_id=1)
    assert result["total_accounts"] == 2
    assert result["total_count"] == 3
    assert {item["account_id"] for item in result["accounts"]} == {1, 2}


def test_list_owned_cards_sort_by_acquired_desc():
    db_engine._engine = create_engine("sqlite:///:memory:")
    SQLModel.metadata.create_all(db_engine._engine)
    _seed_owned_cards_data()

    with Session(db_engine._engine) as session:
        card1_records = session.exec(
            select(AccountCard).where(AccountCard.card_id == 1)
        ).all()
        card2_records = session.exec(
            select(AccountCard).where(AccountCard.card_id == 2)
        ).all()
        card3_records = session.exec(
            select(AccountCard).where(AccountCard.card_id == 3)
        ).all()

        for record in card1_records:
            record.created_at = datetime(2024, 1, 2, 12, 0, 0)
            session.add(record)
        for record in card2_records:
            record.created_at = datetime(2024, 1, 3, 12, 0, 0)
            session.add(record)
        for record in card3_records:
            record.created_at = datetime(2024, 1, 1, 12, 0, 0)
            session.add(record)

        session.commit()

    repo = AccountCardRepository()
    items = repo.list_owned_cards(page=0, page_size=10, sort_by="acquired")
    assert [item["card"].id for item in items] == [2, 1, 3]
