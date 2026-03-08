# -*- coding: utf-8 -*-

"""owned_card_service 交换账号表格上下文测试。"""

import pytest
from sqlmodel import Session

from ptcgp_auto_v2.db.models import Card
from ptcgp_auto_v2.web.services.owned_card_service import (
    build_owned_card_exchange_accounts_context,
)


@pytest.fixture
def card_id(session: Session) -> int:
    """构造测试卡牌。"""
    card = Card(
        set_code="A1",
        number=1,
        name="Test Card",
        rarity="R",
        image_url="test.png",
    )
    session.add(card)
    session.commit()
    session.refresh(card)
    return card.id


@pytest.fixture
def fake_accounts_data(monkeypatch):
    """注入仓储返回，隔离数据库全局连接副作用。"""
    payload = {
        "accounts": [
            {
                "account_id": 1,
                "game_id": "game-alpha",
                "friend_id": "1000000000000001",
                "nickname": "Alpha",
                "count": 2,
                "exchange_points": 1200,
            },
            {
                "account_id": 2,
                "game_id": "game-bravo",
                "friend_id": "1000000000000002",
                "nickname": "Bravo",
                "count": 5,
                "exchange_points": 5000,
            },
            {
                "account_id": 3,
                "game_id": "game-charlie",
                "friend_id": "2000000000000003",
                "nickname": "Charlie",
                "count": 1,
                "exchange_points": None,
            },
            {
                "account_id": 4,
                "game_id": "game-delta",
                "friend_id": "3000000000000004",
                "nickname": "Delta",
                "count": 4,
                "exchange_points": 25000,
            },
        ],
        "total_accounts": 4,
        "total_count": 12,
    }

    monkeypatch.setattr(
        "ptcgp_auto_v2.web.services.owned_card_service.AccountCardRepository.get_owned_card_accounts",
        lambda _self, _card_id: payload,
    )
    monkeypatch.setattr(
        "ptcgp_auto_v2.web.services.owned_card_service.ExchangeCardRequestRepository.has_active_request",
        lambda _self, _account_id: False,
    )


def test_exchange_accounts_context_supports_search(
    session: Session, card_id: int, fake_accounts_data
):
    """应支持按账号 ID/朋友id/昵称进行简单搜索。"""
    context = build_owned_card_exchange_accounts_context(
        session=session,
        card_id=card_id,
        page=0,
        page_size=20,
        q="1000000000000002",
        sort_by="account_id",
        sort_order="asc",
    )

    assert context["total_items"] == 1
    assert len(context["accounts"]) == 1
    assert context["accounts"][0]["friend_id"] == "1000000000000002"


def test_exchange_accounts_context_supports_sort_whitelist(
    session: Session, card_id: int, fake_accounts_data
):
    """应支持白名单排序（按数量降序）。"""
    context = build_owned_card_exchange_accounts_context(
        session=session,
        card_id=card_id,
        page=0,
        page_size=20,
        q="",
        sort_by="count",
        sort_order="desc",
    )

    counts = [item["count"] for item in context["accounts"]]
    assert counts == [5, 4, 2, 1]


def test_exchange_accounts_context_supports_exchange_points_sort(
    session: Session, card_id: int, fake_accounts_data
):
    """应支持按交换点数排序，空值排在末尾。"""
    context = build_owned_card_exchange_accounts_context(
        session=session,
        card_id=card_id,
        page=0,
        page_size=20,
        q="",
        sort_by="exchange_points",
        sort_order="desc",
    )

    account_ids = [item["account_id"] for item in context["accounts"]]
    assert account_ids == [4, 2, 1, 3]


def test_exchange_accounts_context_supports_pagination(
    session: Session, card_id: int, fake_accounts_data
):
    """应支持固定 page_size 的传统分页。"""
    context = build_owned_card_exchange_accounts_context(
        session=session,
        card_id=card_id,
        page=1,
        page_size=2,
        q="",
        sort_by="account_id",
        sort_order="asc",
    )

    assert context["total_items"] == 4
    assert context["page"] == 1
    assert context["page_size"] == 2
    assert context["has_prev"] is True
    assert context["has_next"] is False
    assert len(context["accounts"]) == 2


def test_exchange_accounts_context_returns_enabled_action_by_default(
    session: Session, card_id: int, fake_accounts_data
):
    """满足条件时应返回启用状态的交换动作。"""
    context = build_owned_card_exchange_accounts_context(
        session=session,
        card_id=card_id,
        page=0,
        page_size=20,
        q="",
        sort_by="account_id",
        sort_order="asc",
    )

    action = context["accounts"][0]["exchange_action"]
    assert action["enabled"] is True
    assert action["reason_key"] is None
    assert context["accounts"][0]["exchange_points"] == 1200


def test_exchange_accounts_context_blocks_active_request(monkeypatch, session: Session, card_id: int, fake_accounts_data):
    """有活跃请求时应直接返回禁用按钮和原因。"""
    monkeypatch.setattr(
        "ptcgp_auto_v2.web.services.owned_card_service.ExchangeCardRequestRepository.has_active_request",
        lambda _self, account_id: account_id == 2,
    )

    context = build_owned_card_exchange_accounts_context(
        session=session,
        card_id=card_id,
        page=0,
        page_size=20,
        q="",
        sort_by="account_id",
        sort_order="asc",
    )

    blocked_row = context["accounts"][1]
    assert blocked_row["exchange_action"]["enabled"] is False
    assert blocked_row["exchange_action"]["reason_key"] == "has_active_request"


def test_exchange_accounts_context_blocks_missing_owned_card_first(monkeypatch, session: Session, card_id: int, fake_accounts_data):
    """持有数量不足时应优先返回数量不足原因。"""
    payload = {
        "accounts": [
            {
                "account_id": 9,
                "game_id": "game-zero",
                "friend_id": "9000000000000009",
                "nickname": "Zero",
                "count": 0,
                "exchange_points": 99999,
            }
        ],
        "total_accounts": 1,
        "total_count": 0,
    }
    monkeypatch.setattr(
        "ptcgp_auto_v2.web.services.owned_card_service.AccountCardRepository.get_owned_card_accounts",
        lambda _self, _card_id: payload,
    )
    monkeypatch.setattr(
        "ptcgp_auto_v2.web.services.owned_card_service.ExchangeCardRequestRepository.has_active_request",
        lambda _self, _account_id: True,
    )

    context = build_owned_card_exchange_accounts_context(
        session=session,
        card_id=card_id,
        page=0,
        page_size=20,
        q="",
        sort_by="account_id",
        sort_order="asc",
    )

    action = context["accounts"][0]["exchange_action"]
    assert action["enabled"] is False
    assert action["reason_key"] == "missing_owned_card"


def test_exchange_accounts_context_blocks_non_exchangeable_rarity(monkeypatch, session: Session, fake_accounts_data):
    """不可交换稀有度应优先禁用所有账号按钮。"""
    card = Card(
        set_code="A1",
        number=99,
        name="Blocked Card",
        rarity="UR",
        image_url="blocked.png",
    )
    session.add(card)
    session.commit()
    session.refresh(card)

    context = build_owned_card_exchange_accounts_context(
        session=session,
        card_id=card.id,
        page=0,
        page_size=20,
        q="",
        sort_by="account_id",
        sort_order="asc",
    )

    assert context["accounts"][0]["exchange_action"]["enabled"] is False
    assert context["accounts"][0]["exchange_action"]["reason_key"] == "blocked_rarity"
