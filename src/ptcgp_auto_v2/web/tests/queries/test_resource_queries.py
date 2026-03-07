# -*- coding: utf-8 -*-

from datetime import datetime, timedelta

from sqlmodel import Session

from ptcgp_auto_v2.db.models import Account, AccountPackPoint, AccountStat
from ptcgp_auto_v2.web.queries.resource_queries import (
    list_account_resources,
    list_pack_point_resources,
)


def test_list_account_resources_supports_sort_and_pagination(session: Session):
    """账号资源查询应支持按交换点数排序并分页。"""
    base = datetime.now() - timedelta(minutes=5)

    alpha = Account(
        game_id="resource_acc_alpha",
        friend_id="1000000000000001",
        nickname="Alpha",
        updated_at=base,
    )
    bravo = Account(
        game_id="resource_acc_bravo",
        friend_id="1000000000000002",
        nickname="Bravo",
        updated_at=base + timedelta(minutes=1),
    )
    charlie = Account(
        game_id="resource_acc_charlie",
        friend_id="1000000000000003",
        nickname="Charlie",
        updated_at=base + timedelta(minutes=2),
    )
    session.add_all([alpha, bravo, charlie])
    session.commit()
    session.refresh(alpha)
    session.refresh(bravo)
    session.refresh(charlie)

    session.add_all(
        [
            AccountStat(
                account_id=alpha.id,
                exchange_points=120,
                pack_hourglass_count=10,
            ),
            AccountStat(
                account_id=bravo.id,
                exchange_points=300,
                pack_hourglass_count=20,
            ),
        ]
    )
    session.commit()

    rows, total = list_account_resources(
        session=session,
        q="",
        sort_by="exchange_points",
        sort_order="desc",
        page=0,
        page_size=2,
    )

    assert total == 3
    assert [row["nickname"] for row in rows] == ["Bravo", "Alpha"]

    page_two_rows, _ = list_account_resources(
        session=session,
        q="",
        sort_by="exchange_points",
        sort_order="desc",
        page=1,
        page_size=2,
    )

    assert len(page_two_rows) == 1
    assert page_two_rows[0]["nickname"] == "Charlie"
    assert page_two_rows[0]["exchange_points"] is None


def test_list_account_resources_supports_search_by_nickname_and_friend_id(
    session: Session,
):
    """账号资源查询应支持昵称和朋友id搜索。"""
    target = Account(
        game_id="resource_search_target",
        friend_id="1234567890123456",
        nickname="SearchHero",
    )
    other = Account(
        game_id="resource_search_other",
        friend_id="9999999999999999",
        nickname="Other",
    )
    session.add_all([target, other])
    session.commit()

    nickname_rows, nickname_total = list_account_resources(
        session=session,
        q="hero",
        sort_by="id",
        sort_order="asc",
        page=0,
        page_size=10,
    )
    assert nickname_total == 1
    assert nickname_rows[0]["nickname"] == "SearchHero"

    friend_rows, friend_total = list_account_resources(
        session=session,
        q="3456",
        sort_by="id",
        sort_order="asc",
        page=0,
        page_size=10,
    )
    assert friend_total == 1
    assert friend_rows[0]["friend_id"] == "1234567890123456"


def test_list_pack_point_resources_supports_series_sort_and_series_list(
    session: Session,
):
    """包点数查询应支持系列排序、series_list 与缺失值稳定排后。"""
    alpha = Account(
        game_id="pack_point_alpha",
        friend_id="2000000000000001",
        nickname="Alpha",
    )
    bravo = Account(
        game_id="pack_point_bravo",
        friend_id="2000000000000002",
        nickname="Bravo",
    )
    charlie = Account(
        game_id="pack_point_charlie",
        friend_id="2000000000000003",
        nickname="Charlie",
    )
    session.add_all([alpha, bravo, charlie])
    session.commit()
    session.refresh(alpha)
    session.refresh(bravo)
    session.refresh(charlie)

    session.add_all(
        [
            AccountPackPoint(account_id=alpha.id, series="A1", points=30),
            AccountPackPoint(account_id=alpha.id, series="A2", points=5),
            AccountPackPoint(account_id=bravo.id, series="A1", points=80),
            AccountPackPoint(account_id=charlie.id, series="A2", points=99),
        ]
    )
    session.commit()

    result = list_pack_point_resources(
        session=session,
        q="",
        sort_by="series:A1",
        sort_order="desc",
        page=0,
        page_size=10,
    )

    assert result["total"] == 3
    assert result["series_list"] == ["A1", "A2"]
    assert [row["nickname"] for row in result["rows"]] == ["Bravo", "Alpha", "Charlie"]
    assert result["rows"][0]["series_points"] == {"A1": 80}
    assert result["rows"][1]["series_points"] == {"A1": 30, "A2": 5}
    assert result["rows"][2]["series_points"] == {"A2": 99}
