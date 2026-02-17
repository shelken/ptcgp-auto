# -*- coding: utf-8 -*-

from datetime import datetime, timedelta

from sqlmodel import Session

from ptcgp_auto_v2.db.models import Account, ExchangeCardRequest
from ptcgp_auto_v2.web.queries.exchange_card_queries import list_exchange_requests


def test_list_exchange_requests_supports_search_sort_and_pagination(session: Session):
    """交换记录应支持 q 搜索、排序与分页。"""
    account_a = Account(
        game_id="ex_qs_a", friend_id="1000000000000001", nickname="Alpha"
    )
    account_b = Account(
        game_id="ex_qs_b", friend_id="1000000000000002", nickname="Bravo"
    )
    session.add(account_a)
    session.add(account_b)
    session.commit()
    session.refresh(account_a)
    session.refresh(account_b)

    base = datetime.now() - timedelta(minutes=10)
    rows = [
        ExchangeCardRequest(
            from_account_id=account_a.id,
            to_account_id=account_b.id,
            to_friend_id="1111222233334444",
            target_card_id=1,
            target_card_rarity="R",
            status="sending",
            created_at=base,
            updated_at=base,
        ),
        ExchangeCardRequest(
            from_account_id=account_a.id,
            to_account_id=account_b.id,
            to_friend_id="9999000011112222",
            target_card_id=2,
            target_card_rarity="RR",
            status="completed",
            created_at=base + timedelta(minutes=1),
            updated_at=base + timedelta(minutes=1),
        ),
        ExchangeCardRequest(
            from_account_id=account_b.id,
            to_account_id=account_a.id,
            to_friend_id="5555666677778888",
            target_card_id=3,
            target_card_rarity="AR",
            status="failed",
            created_at=base + timedelta(minutes=2),
            updated_at=base + timedelta(minutes=2),
        ),
    ]
    session.add_all(rows)
    session.commit()

    filtered, total = list_exchange_requests(
        session=session,
        account_id=None,
        status=None,
        q="9999",
        sort_by="target_card_id",
        sort_order="desc",
        page=0,
        page_size=10,
    )
    assert total == 1
    assert len(filtered) == 1
    assert filtered[0].to_friend_id == "9999000011112222"

    paged, total_all = list_exchange_requests(
        session=session,
        account_id=None,
        status=None,
        q="",
        sort_by="created_at",
        sort_order="asc",
        page=1,
        page_size=2,
    )
    assert total_all == 3
    assert len(paged) == 1
    assert paged[0].target_card_id == 3
