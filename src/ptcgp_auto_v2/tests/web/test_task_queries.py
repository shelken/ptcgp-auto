# -*- coding: utf-8 -*-

from datetime import datetime, timedelta

from sqlmodel import Session, SQLModel, create_engine, select

from ptcgp_auto_v2.db.models import TaskInstance
from ptcgp_auto_v2.web.queries.task_queries import reset_completed_task_instances


def test_reset_completed_tasks_clears_next_run_at_for_manual_priority_boost():
    """手动重置已完成任务后，应清空 next_run_at 以提升调度优先级。"""
    engine = create_engine("sqlite:///:memory:")
    SQLModel.metadata.create_all(engine)

    future_time = datetime.now() + timedelta(hours=6)

    with Session(engine) as session:
        normal_task = TaskInstance(
            account_id=1,
            task_type="open_pack",
            status="completed",
            next_run_at=future_time,
        )
        init_task = TaskInstance(
            account_id=1,
            task_type="init_account",
            status="completed",
            next_run_at=future_time,
        )
        session.add(normal_task)
        session.add(init_task)
        session.commit()

        reset_count = reset_completed_task_instances(
            session=session,
            status=[],
            task_type=[],
            account_id=None,
        )

        refreshed_normal = session.exec(
            select(TaskInstance).where(TaskInstance.id == normal_task.id)
        ).one()
        refreshed_init = session.exec(
            select(TaskInstance).where(TaskInstance.id == init_task.id)
        ).one()

    assert reset_count == 1
    assert refreshed_normal.status == "pending"
    assert refreshed_normal.next_run_at is None
    assert refreshed_init.status == "completed"
    assert refreshed_init.next_run_at is not None
