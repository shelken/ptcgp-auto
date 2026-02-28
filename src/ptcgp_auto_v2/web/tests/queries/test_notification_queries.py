# -*- coding: utf-8 -*-

from datetime import datetime, timedelta

from sqlmodel import Session

from ptcgp_auto_v2.db.models import Card, CardPack, Notification
from ptcgp_auto_v2.web.queries.notification_queries import (
    list_notification_selectable_cards,
    list_notifications,
    list_recent_notifications,
)


def _seed_notifications(session: Session) -> None:
    """写入通知测试数据。"""
    base = datetime.now() - timedelta(minutes=3)
    rows = [
        Notification(
            scene="task_status",
            title="任务失败",
            content="账号 1 执行失败",
            related_account_id=1,
            is_read=False,
            created_at=base,
        ),
        Notification(
            scene="rare_card_obtained",
            title="获得稀有卡",
            content="账号 2 获得 RR",
            related_account_id=2,
            is_read=True,
            created_at=base + timedelta(minutes=1),
        ),
        Notification(
            scene="system_warning",
            title="系统告警",
            content="设备断连",
            related_account_id=None,
            is_read=False,
            created_at=base + timedelta(minutes=2),
        ),
    ]
    session.add_all(rows)
    session.commit()


def test_list_notifications_supports_filters_and_pagination(session: Session):
    """通知查询应支持筛选与分页。"""
    _seed_notifications(session)

    rows, total = list_notifications(
        session=session,
        scene="task_status",
        account_id=1,
        is_read=False,
        page=0,
        page_size=10,
    )
    assert total == 1
    assert len(rows) == 1
    assert rows[0].title == "任务失败"


def test_list_notifications_supports_q_and_sort(session: Session):
    """通知查询应支持 q 搜索与排序。"""
    _seed_notifications(session)

    rows, total = list_notifications(
        session=session,
        q="账号 2",
        sort_by="title",
        sort_order="asc",
        page=0,
        page_size=10,
    )
    assert total == 1
    assert len(rows) == 1
    assert rows[0].related_account_id == 2


def test_list_recent_notifications_returns_latest(session: Session):
    """最近通知应按时间倒序返回。"""
    _seed_notifications(session)
    rows = list_recent_notifications(session=session, limit=2)
    assert len(rows) == 2
    assert rows[0].title == "系统告警"


def test_list_notification_selectable_cards_uses_pagination(session: Session):
    """卡牌选择器必须分页，不允许全量返回。"""
    cards = [
        Card(
            id=910001 + idx,
            set_code="A1",
            number=idx,
            name=f"Card-{idx}",
            rarity="R",
            image_url=f"https://example.com/{idx}.png",
        )
        for idx in range(1, 41)
    ]
    session.add_all(cards)
    session.commit()

    rows, total = list_notification_selectable_cards(
        session=session,
        page=0,
        page_size=24,
    )
    assert total == 40
    assert len(rows) == 24


def test_list_notification_selectable_cards_supports_pack_filter(session: Session):
    """卡牌选择器应支持按子包过滤。"""
    session.add_all(
        [
            Card(
                id=920001,
                set_code="A1",
                number=1,
                name="Pack A",
                rarity="RR",
                image_url="https://example.com/a.png",
            ),
            Card(
                id=920002,
                set_code="A1",
                number=2,
                name="Pack B",
                rarity="RR",
                image_url="https://example.com/b.png",
            ),
            CardPack(card_id=920001, pack_name="Mewtwo"),
            CardPack(card_id=920002, pack_name="Charizard"),
        ]
    )
    session.commit()

    rows, total = list_notification_selectable_cards(
        session=session,
        pack_name="Mewtwo",
        page=0,
        page_size=24,
    )
    assert total == 1
    assert len(rows) == 1
    assert rows[0].id == 920001


def test_list_notification_selectable_cards_supports_localized_name_search(
    session: Session,
):
    """卡牌选择器搜索应命中 data.localized_name。"""
    session.add(
        Card(
            id=920003,
            set_code="A1",
            number=3,
            name="Card EN",
            rarity="RR",
            image_url="https://example.com/c.png",
            data='{"localized_name":{"zh":"卡牌中文名"}}',
        )
    )
    session.commit()

    rows, total = list_notification_selectable_cards(
        session=session,
        q="中文名",
        page=0,
        page_size=24,
    )
    assert total == 1
    assert len(rows) == 1
    assert rows[0].id == 920003
