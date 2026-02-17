# -*- coding: utf-8 -*-

from datetime import datetime, timedelta

from sqlmodel import Session

from ptcgp_auto_v2.db.models import Account, AccountGiftRecord
from ptcgp_auto_v2.web.services.daily_gift_service import build_daily_gift_context


def test_daily_gift_context_supports_record_search_sort_pagination(session: Session):
    """daily-gift 记录列表应支持 q/sort/page/page_size 协议。"""
    account_a = Account(
        game_id="dg_qs_a", friend_id="5000000000000001", nickname="Alpha"
    )
    account_b = Account(
        game_id="dg_qs_b", friend_id="5000000000000002", nickname="Bravo"
    )
    session.add(account_a)
    session.add(account_b)
    session.commit()
    session.refresh(account_a)
    session.refresh(account_b)

    base = datetime.now() - timedelta(minutes=10)
    rows = [
        AccountGiftRecord(
            account_id=account_a.id,
            target_account_id=account_b.id,
            target_friend_id=account_b.friend_id,
            biz_date_local="2026-02-17",
            status="success",
            updated_at=base,
        ),
        AccountGiftRecord(
            account_id=account_a.id,
            target_account_id=account_b.id,
            target_friend_id="5000000000009999",
            biz_date_local="2026-02-17",
            status="failed",
            updated_at=base + timedelta(minutes=1),
        ),
        AccountGiftRecord(
            account_id=account_b.id,
            target_account_id=account_a.id,
            target_friend_id=account_a.friend_id,
            biz_date_local="2026-02-17",
            status="waiting",
            updated_at=base + timedelta(minutes=2),
        ),
    ]
    session.add_all(rows)
    session.commit()

    context = build_daily_gift_context(
        session=session,
        lang="zh_CN",
        biz_date_local="2026-02-17",
        q="9999",
        sort_by="updated_at",
        sort_order="desc",
        page=0,
        page_size=10,
    )
    assert context["records_total"] == 1
    assert len(context["records"]) == 1
    assert context["records"][0]["target_friend_id"] == "5000000000009999"

    paged = build_daily_gift_context(
        session=session,
        lang="zh_CN",
        biz_date_local="2026-02-17",
        q="",
        sort_by="updated_at",
        sort_order="asc",
        page=1,
        page_size=2,
    )
    assert paged["records_total"] == 3
    assert len(paged["records"]) == 1
    assert paged["has_prev"] is True
    assert paged["has_next"] is False
