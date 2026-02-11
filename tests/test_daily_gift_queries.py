# -*- coding: utf-8 -*-

from datetime import datetime

from sqlmodel import Session

from ptcgp_auto_v2.db.models import Account, AccountGiftPair, AccountGiftRecord
from ptcgp_auto_v2.web.queries.daily_gift_queries import (
    list_active_gift_pairs,
    list_daily_gift_records,
)


def test_list_daily_gift_records_filters_by_biz_date(session: Session):
    """应仅返回指定业务日期的送卡记录。"""
    account = Account(game_id="gift_query_acc_1", friend_id="1000000000000001")
    session.add(account)
    session.commit()
    session.refresh(account)

    row_today = AccountGiftRecord(
        account_id=account.id,
        target_friend_id="2000000000000001",
        biz_date_local="2026-02-11",
        status="success",
    )
    row_other_day = AccountGiftRecord(
        account_id=account.id,
        target_friend_id="2000000000000002",
        biz_date_local="2026-02-10",
        status="failed",
    )
    session.add(row_today)
    session.add(row_other_day)
    session.commit()

    rows = list_daily_gift_records(session=session, biz_date_local="2026-02-11")
    assert len(rows) == 1
    assert rows[0].target_friend_id == "2000000000000001"


def test_list_active_gift_pairs_only_returns_active_rows(session: Session):
    """应仅返回当前有效的配对记录。"""
    account_a = Account(game_id="gift_query_acc_2", friend_id="1000000000000002")
    account_b = Account(game_id="gift_query_acc_3", friend_id="1000000000000003")
    session.add(account_a)
    session.add(account_b)
    session.commit()
    session.refresh(account_a)
    session.refresh(account_b)

    active_pair = AccountGiftPair(
        account_id=account_a.id,
        target_account_id=account_b.id,
        target_friend_id=account_b.friend_id,
        strategy="fixed_card_a1_153",
        is_active=True,
        created_at=datetime.now(),
        updated_at=datetime.now(),
    )
    inactive_pair = AccountGiftPair(
        account_id=account_b.id,
        target_account_id=account_a.id,
        target_friend_id=account_a.friend_id,
        strategy="fixed_card_a1_153",
        is_active=False,
        created_at=datetime.now(),
        updated_at=datetime.now(),
    )
    session.add(active_pair)
    session.add(inactive_pair)
    session.commit()

    rows = list_active_gift_pairs(session=session)
    assert len(rows) == 1
    assert rows[0].account_id == account_a.id
