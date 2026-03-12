# -*- coding: utf-8 -*-

from datetime import datetime, timedelta

from sqlmodel import Session

from ptcgp_auto_v2.db.models import Account, AccountGiftPair, AccountGiftRecord
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
    assert context["stats"]["total"] == 3

    paged = build_daily_gift_context(
        session=session,
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


def test_daily_gift_context_record_total_is_not_capped_at_200(session: Session):
    """daily-gift 记录列表总数不应被 200 条硬截断。"""
    account = Account(game_id="dg_many_a", friend_id="6000000000000001", nickname="Many")
    session.add(account)
    session.commit()
    session.refresh(account)

    base = datetime.now() - timedelta(hours=1)
    rows: list[AccountGiftRecord] = []
    for index in range(205):
        rows.append(
            AccountGiftRecord(
                account_id=account.id,
                target_account_id=None,
                target_friend_id=f"600000000000{index:04d}",
                biz_date_local="2026-02-18",
                status="success" if index % 2 == 0 else "waiting",
                updated_at=base + timedelta(seconds=index),
            )
        )
    session.add_all(rows)
    session.commit()

    context = build_daily_gift_context(
        session=session,
        biz_date_local="2026-02-18",
        page=20,
        page_size=10,
    )

    assert context["records_total"] == 205
    assert context["stats"]["total"] == 205
    assert len(context["records"]) == 5
    assert context["has_prev"] is True
    assert context["has_next"] is False


def test_daily_gift_context_pair_progress_supports_account_filter_and_pagination(
    session: Session,
):
    """配对互送进度应支持账号过滤与独立分页。"""
    account_a = Account(game_id="dg_pair_a", friend_id="7000000000000001", nickname="A")
    account_b = Account(game_id="dg_pair_b", friend_id="7000000000000002", nickname="B")
    account_c = Account(game_id="dg_pair_c", friend_id="7000000000000003", nickname="C")
    account_d = Account(game_id="dg_pair_d", friend_id="7000000000000004", nickname="D")
    session.add_all([account_a, account_b, account_c, account_d])
    session.commit()
    session.refresh(account_a)
    session.refresh(account_b)
    session.refresh(account_c)
    session.refresh(account_d)

    session.add_all(
        [
            AccountGiftPair(
                account_id=account_a.id,
                target_account_id=account_b.id,
                target_friend_id=account_b.friend_id,
                is_active=True,
            ),
            AccountGiftPair(
                account_id=account_b.id,
                target_account_id=account_a.id,
                target_friend_id=account_a.friend_id,
                is_active=True,
            ),
            AccountGiftPair(
                account_id=account_c.id,
                target_account_id=account_d.id,
                target_friend_id=account_d.friend_id,
                is_active=True,
            ),
            AccountGiftPair(
                account_id=account_d.id,
                target_account_id=account_c.id,
                target_friend_id=account_c.friend_id,
                is_active=True,
            ),
        ]
    )

    base = datetime.now() - timedelta(minutes=30)
    session.add_all(
        [
            AccountGiftRecord(
                account_id=account_a.id,
                target_account_id=account_b.id,
                target_friend_id=account_b.friend_id,
                biz_date_local="2026-02-19",
                status="success",
                updated_at=base,
            ),
            AccountGiftRecord(
                account_id=account_b.id,
                target_account_id=account_a.id,
                target_friend_id=account_a.friend_id,
                biz_date_local="2026-02-19",
                status="failed",
                error_code="TARGET_BUSY",
                updated_at=base + timedelta(minutes=1),
            ),
            AccountGiftRecord(
                account_id=account_c.id,
                target_account_id=account_d.id,
                target_friend_id=account_d.friend_id,
                biz_date_local="2026-02-19",
                status="waiting",
                updated_at=base + timedelta(minutes=2),
            ),
        ]
    )
    session.commit()

    filtered = build_daily_gift_context(
        session=session,
        biz_date_local="2026-02-19",
        account_id=account_a.id,
        pair_page=0,
        pair_page_size=10,
    )
    assert filtered["pair_total"] == 1
    assert len(filtered["pair_send_status_rows"]) == 1
    assert filtered["pair_send_status_rows"][0]["left_to_right_status"] == "success"
    assert filtered["pair_send_status_rows"][0]["right_to_left_status"] == "failed"
    assert filtered["stats"]["total"] == 2

    paged = build_daily_gift_context(
        session=session,
        biz_date_local="2026-02-19",
        pair_page=1,
        pair_page_size=1,
    )
    assert paged["pair_total"] == 2
    assert len(paged["pair_send_status_rows"]) == 1
    assert paged["pair_has_prev"] is True
    assert paged["pair_has_next"] is False
