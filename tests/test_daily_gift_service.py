# -*- coding: utf-8 -*-

from sqlmodel import Session

from ptcgp_auto_v2.db.models import Account, AccountGiftPair, AccountGiftRecord
from ptcgp_auto_v2.web.services.daily_gift_service import build_daily_gift_context


def test_build_daily_gift_context_merges_bidirectional_pair(session: Session):
    """双向稳定关系应合并为一张配对卡片。"""
    account_a = Account(game_id="gift_service_acc_1", friend_id="3000000000000001")
    account_b = Account(game_id="gift_service_acc_2", friend_id="3000000000000002")
    session.add(account_a)
    session.add(account_b)
    session.commit()
    session.refresh(account_a)
    session.refresh(account_b)

    pair_ab = AccountGiftPair(
        account_id=account_a.id,
        target_account_id=account_b.id,
        target_friend_id=account_b.friend_id,
        is_active=True,
    )
    pair_ba = AccountGiftPair(
        account_id=account_b.id,
        target_account_id=account_a.id,
        target_friend_id=account_a.friend_id,
        is_active=True,
    )
    session.add(pair_ab)
    session.add(pair_ba)
    session.commit()

    context = build_daily_gift_context(
        session=session,
        lang="zh_CN",
        biz_date_local="2026-02-11",
    )

    assert len(context["pair_cards"]) == 1
    pair_ids = {
        context["pair_cards"][0]["left_account_id"],
        context["pair_cards"][0]["right_account_id"],
    }
    assert pair_ids == {account_a.id, account_b.id}
    assert context["pair_anomalies"] == []


def test_build_daily_gift_context_marks_single_direction_as_anomaly(session: Session):
    """单边关系应落入异常分组，便于管理中心排查。"""
    account_c = Account(game_id="gift_service_acc_3", friend_id="3000000000000003")
    account_d = Account(game_id="gift_service_acc_4", friend_id="3000000000000004")
    session.add(account_c)
    session.add(account_d)
    session.commit()
    session.refresh(account_c)
    session.refresh(account_d)

    single_pair = AccountGiftPair(
        account_id=account_c.id,
        target_account_id=account_d.id,
        target_friend_id=account_d.friend_id,
        is_active=True,
    )
    session.add(single_pair)
    session.commit()

    context = build_daily_gift_context(
        session=session,
        lang="zh_CN",
        biz_date_local="2026-02-11",
    )

    assert context["pair_cards"] == []
    assert len(context["pair_anomalies"]) == 1
    assert context["pair_anomalies"][0]["reason_code"] == "single_direction"
    assert context["pair_anomalies"][0]["account_id"] == account_c.id
    assert context["pair_anomalies"][0]["target_account_id"] == account_d.id


def test_build_daily_gift_context_normalizes_invalid_biz_date(session: Session):
    """非法业务日期应自动回退到当天，并返回最近日期选项。"""
    context = build_daily_gift_context(
        session=session,
        lang="zh_CN",
        biz_date_local="invalid-date",
    )

    assert len(context["selected_biz_date_local"]) == 10
    assert len(context["recent_biz_dates"]) == 7
    assert context["recent_biz_dates"][0] == context["selected_biz_date_local"]


def test_build_daily_gift_context_contains_pair_send_status_rows(session: Session):
    """每日送卡情况应按配对输出双向互送状态。"""
    account_a = Account(game_id="gift_pair_status_a", friend_id="4000000000000001")
    account_b = Account(game_id="gift_pair_status_b", friend_id="4000000000000002")
    session.add(account_a)
    session.add(account_b)
    session.commit()
    session.refresh(account_a)
    session.refresh(account_b)

    session.add(
        AccountGiftPair(
            account_id=account_a.id,
            target_account_id=account_b.id,
            target_friend_id=account_b.friend_id,
            is_active=True,
        )
    )
    session.add(
        AccountGiftPair(
            account_id=account_b.id,
            target_account_id=account_a.id,
            target_friend_id=account_a.friend_id,
            is_active=True,
        )
    )
    session.add(
        AccountGiftRecord(
            account_id=account_a.id,
            target_account_id=account_b.id,
            target_friend_id=account_b.friend_id,
            biz_date_local="2026-02-11",
            status="success",
        )
    )
    session.add(
        AccountGiftRecord(
            account_id=account_b.id,
            target_account_id=account_a.id,
            target_friend_id=account_a.friend_id,
            biz_date_local="2026-02-11",
            status="failed",
            error_code="NETWORK",
        )
    )
    session.commit()

    context = build_daily_gift_context(
        session=session,
        lang="zh_CN",
        biz_date_local="2026-02-11",
    )

    assert len(context["pair_send_status_rows"]) == 1
    row = context["pair_send_status_rows"][0]
    assert row["left_to_right_status"] == "success"
    assert row["right_to_left_status"] == "failed"
    assert row["pair_progress"] == "single_success"
