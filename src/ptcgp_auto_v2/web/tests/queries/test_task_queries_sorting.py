# -*- coding: utf-8 -*-
"""任务查询排序测试。"""

from sqlmodel import Session, SQLModel, create_engine

from ptcgp_auto_v2.db.models import Account, TaskInstance
from ptcgp_auto_v2.web.queries.task_queries import fetch_task_instances


def test_fetch_task_instances_sorts_by_last_duration_with_nulls_last():
    """按上次耗时排序时，空值应固定排最后。"""
    engine = create_engine("sqlite:///:memory:")
    SQLModel.metadata.create_all(engine)

    with Session(engine) as session:
        account = Account(game_id="task-query-account", nickname="query-user")
        session.add(account)
        session.commit()
        session.refresh(account)

        fast_task = TaskInstance(
            account_id=account.id,
            task_type="open_pack",
            status="completed",
            last_duration_seconds=15,
        )
        slow_task = TaskInstance(
            account_id=account.id,
            task_type="claim_gifts",
            status="completed",
            last_duration_seconds=90,
        )
        unknown_task = TaskInstance(
            account_id=account.id,
            task_type="wonder_pick",
            status="completed",
            last_duration_seconds=None,
        )
        session.add(fast_task)
        session.add(slow_task)
        session.add(unknown_task)
        session.commit()

        asc_items, _, total = fetch_task_instances(
            session=session,
            page=0,
            page_size=10,
            status=[],
            task_type=[],
            account_id=None,
            sort_by="last_duration_seconds",
            sort_order="asc",
        )
        desc_items, _, _ = fetch_task_instances(
            session=session,
            page=0,
            page_size=10,
            status=[],
            task_type=[],
            account_id=None,
            sort_by="last_duration_seconds",
            sort_order="desc",
        )

    assert total == 3
    assert [item.last_duration_seconds for item in asc_items] == [15, 90, None]
    assert [item.last_duration_seconds for item in desc_items] == [90, 15, None]
