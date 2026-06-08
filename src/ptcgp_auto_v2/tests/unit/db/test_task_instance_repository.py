# -*- coding: utf-8 -*-
"""TaskInstanceRepository 行为测试。"""

from datetime import datetime

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


def test_update_scheduling_fields_updates_managed_instances_from_list_by_account(tmp_path):
    """同一 Session 内重算托管实例时，调度变化应刷新更新时间。"""
    db_path = tmp_path / "task_instances.db"
    engine = create_engine(f"sqlite:///{db_path}")
    SQLModel.metadata.create_all(engine)
    next_run_at = datetime(2026, 1, 4, 3, 4, 5)

    with Session(engine) as session:
        instance = TaskInstance(
            account_id=9,
            task_type="open_pack",
            status=TaskStatus.PENDING.value,
            reset_type="daily",
        )
        session.add(instance)
        session.commit()
        session.refresh(instance)
        instance_id = instance.id
        original_updated_at = instance.updated_at

    assert instance_id is not None

    with Session(engine) as session:
        repo = TaskInstanceRepository(session)
        instances = repo.list_by_account(9)
        assert [instance.id for instance in instances] == [instance_id]

        instances[0].reset_type = "weekly"
        instances[0].next_run_at = next_run_at
        changed = repo.update_scheduling_fields(instances)
        session.commit()

    with Session(engine) as session:
        saved = session.get(TaskInstance, instance_id)

    assert changed == 1
    assert saved is not None
    assert saved.reset_type == "weekly"
    assert saved.next_run_at == next_run_at
    assert saved.updated_at > original_updated_at


def test_update_scheduling_fields_counts_duplicate_id_once_with_last_value(tmp_path):
    """同一任务实例重复出现时，只按最终调度值更新一次。"""
    db_path = tmp_path / "task_instances.db"
    engine = create_engine(f"sqlite:///{db_path}")
    SQLModel.metadata.create_all(engine)
    first_next_run_at = datetime(2026, 1, 2, 3, 4, 5)
    final_next_run_at = datetime(2026, 1, 3, 3, 4, 5)

    with Session(engine) as session:
        instance = TaskInstance(
            account_id=9,
            task_type="open_pack",
            status=TaskStatus.PENDING.value,
            reset_type="daily",
        )
        session.add(instance)
        session.commit()
        session.refresh(instance)
        instance_id = instance.id
        original_updated_at = instance.updated_at

    assert instance_id is not None

    with Session(engine) as session:
        changed = TaskInstanceRepository(session).update_scheduling_fields(
            [
                TaskInstance(
                    id=instance_id,
                    account_id=9,
                    task_type="open_pack",
                    reset_type="daily",
                    next_run_at=first_next_run_at,
                ),
                TaskInstance(
                    id=instance_id,
                    account_id=9,
                    task_type="open_pack",
                    reset_type="weekly",
                    next_run_at=final_next_run_at,
                ),
            ]
        )
        session.commit()

    with Session(engine) as session:
        saved = session.get(TaskInstance, instance_id)

    assert changed == 1
    assert saved is not None
    assert saved.reset_type == "weekly"
    assert saved.next_run_at == final_next_run_at
    assert saved.updated_at > original_updated_at
