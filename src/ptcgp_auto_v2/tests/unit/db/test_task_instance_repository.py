# -*- coding: utf-8 -*-
"""TaskInstanceRepository 行为测试。"""

from sqlmodel import Session, SQLModel, create_engine

from ptcgp_auto_v2.core.task_status import TaskStatus
from ptcgp_auto_v2.db.models import TaskInstance
from ptcgp_auto_v2.db.repositories.task_instance_repository import TaskInstanceRepository


def test_set_status_for_ids_clears_stale_error_when_marking_running(tmp_path):
    """任务重新进入 running 时不能保留上一次失败原因。"""
    db_path = tmp_path / "task_instances.db"
    engine = create_engine(f"sqlite:///{db_path}")
    SQLModel.metadata.create_all(engine)

    with Session(engine) as session:
        instance = TaskInstance(
            account_id=9,
            task_type="claim_gifts",
            status=TaskStatus.FAILED.value,
            error_message="连续 15 次停留在同一页面: popup_ok",
        )
        session.add(instance)
        session.commit()
        session.refresh(instance)
        instance_id = instance.id

    assert instance_id is not None

    with Session(engine) as session:
        updated = TaskInstanceRepository(session).set_status_for_ids(
            [instance_id],
            TaskStatus.RUNNING.value,
        )
        session.commit()

    with Session(engine) as session:
        saved = session.get(TaskInstance, instance_id)

    assert updated == 1
    assert saved is not None
    assert saved.status == TaskStatus.RUNNING.value
    assert saved.error_message is None
