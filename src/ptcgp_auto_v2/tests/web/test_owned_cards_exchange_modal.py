# -*- coding: utf-8 -*-

from unittest.mock import patch

import pytest
from sqlmodel import Session, SQLModel, create_engine

from ptcgp_auto_v2.db.models import Account, AccountCard, Card
from ptcgp_auto_v2.web.services.owned_card_service import build_owned_card_modal_context


@pytest.fixture(name="engine")
def engine_fixture():
    """创建内存数据库引擎。"""
    engine = create_engine("sqlite:///:memory:")
    SQLModel.metadata.create_all(engine)
    return engine


@pytest.fixture(name="mock_get_engine")
def mock_get_engine_fixture(engine):
    """将仓储引擎替换为测试引擎。"""
    with patch(
        "ptcgp_auto_v2.db.repositories.account_card_repository.get_engine",
        return_value=engine,
    ):
        yield


def test_owned_card_modal_only_allows_exchange_when_count_gt_zero(
    engine,
    mock_get_engine,
):
    """账号卡牌数量为 0 时不应出现交换入口。"""
    with Session(engine) as session:
        card = Card(
            set_code="A1",
            number=99,
            name="Test Card",
            rarity="RR",
            image_url="https://example.com/card.png",
        )
        session.add(card)

        sender_a = Account(game_id="g-1", nickname="a", friend_id="1111222233334444")
        sender_b = Account(game_id="g-2", nickname="b", friend_id="5555666677778888")
        session.add(sender_a)
        session.add(sender_b)
        session.commit()
        assert card.id is not None
        assert sender_a.id is not None
        assert sender_b.id is not None
        card_id = card.id
        sender_a_id = sender_a.id
        sender_b_id = sender_b.id

        session.add(
            AccountCard(
                account_id=sender_a_id,
                card_id=card_id,
                count=0,
            )
        )
        session.add(
            AccountCard(
                account_id=sender_b_id,
                card_id=card_id,
                count=2,
            )
        )
        session.commit()

        context = build_owned_card_modal_context(session, card_id, "zh_CN")

    assert context is not None
    exchange_accounts = context.get("exchange_accounts", [])
    assert len(exchange_accounts) == 1
    assert exchange_accounts[0]["account_id"] == sender_b_id
