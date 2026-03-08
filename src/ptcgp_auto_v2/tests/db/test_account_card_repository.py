# -*- coding: utf-8 -*-
from unittest.mock import patch

import pytest
from sqlmodel import Session, SQLModel, create_engine

from ptcgp_auto_v2.db.models import Account, AccountCard, Card
from ptcgp_auto_v2.db.repositories.account_card_repository import (
    AccountCardRepository,
)


@pytest.fixture(name="engine")
def engine_fixture():
    engine = create_engine("sqlite:///:memory:")
    SQLModel.metadata.create_all(engine)
    return engine


@pytest.fixture(name="mock_get_engine")
def mock_get_engine_fixture(engine):
    with patch(
        "ptcgp_auto_v2.db.repositories.account_card_repository.get_engine",
        return_value=engine,
    ):
        yield


def seed_account_cards(engine):
    with Session(engine) as session:
        account1 = Account(
            game_id="game-search-alpha",
            friend_id="1000000000000001",
            nickname="Alpha",
        )
        account2 = Account(
            game_id="game-search-bravo",
            friend_id="1000000000000002",
            nickname="Bravo",
        )
        session.add(account1)
        session.add(account2)

        card1 = Card(
            set_code="A1",
            number=1,
            name="Card1",
            rarity="RR",
            image_url="url1",
        )
        card2 = Card(
            set_code="A1",
            number=2,
            name="Card2",
            rarity="SR",
            image_url="url2",
        )
        session.add(card1)
        session.add(card2)
        session.commit()

        session.add(
            AccountCard(
                account_id=account1.id,
                card_id=card1.id,
                count=2,
            )
        )
        session.add(
            AccountCard(
                account_id=account1.id,
                card_id=card2.id,
                count=1,
            )
        )
        session.add(
            AccountCard(
                account_id=account2.id,
                card_id=card2.id,
                count=3,
            )
        )
        session.commit()

        return account1.id, account2.id


def test_list_owned_cards_with_account_filter(engine, mock_get_engine):
    seed_account_cards(engine)
    repo = AccountCardRepository()

    items = repo.list_owned_cards(
        page=0,
        page_size=20,
        account_query="game-search-alpha",
    )

    assert len(items) == 2
    total_counts = {item["card"].number: item["total_count"] for item in items}
    account_counts = {
        item["card"].number: item["owned_accounts_count"] for item in items
    }
    assert total_counts == {1: 2, 2: 1}
    assert account_counts == {1: 1, 2: 1}


@pytest.mark.parametrize(
    ("account_query", "expected_numbers"),
    [
        ("1", {1, 2}),
        ("Alpha", {1, 2}),
        ("1000000000000001", {1, 2}),
        ("game-search-alpha", {1, 2}),
    ],
)
def test_list_owned_cards_supports_account_search_fields(
    engine, mock_get_engine, account_query, expected_numbers
):
    """拥有卡牌查询应支持账号 ID 之外的四字段搜索。"""
    seed_account_cards(engine)
    repo = AccountCardRepository()

    items = repo.list_owned_cards(
        page=0,
        page_size=20,
        account_query=account_query,
    )

    assert {item["card"].number for item in items} == expected_numbers
