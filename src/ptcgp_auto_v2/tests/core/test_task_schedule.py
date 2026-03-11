from datetime import datetime
from types import SimpleNamespace

from ptcgp_auto_v2.core.task_base import ResetType
from ptcgp_auto_v2.core import task_schedule
from ptcgp_auto_v2.core.task_status import TaskStatus


class DummyTask:
    reset_type = ResetType.DAILY


def _dt(value: str) -> datetime:
    return datetime.strptime(value, "%Y-%m-%d %H:%M:%S")


def test_effective_reset_type_prefers_config():
    reset_type = task_schedule.get_effective_reset_type(
        DummyTask, {"reset_type": "interval"}
    )
    assert reset_type == ResetType.INTERVAL


def test_next_run_at_daily():
    result = task_schedule.compute_next_run_at(
        _dt("2026-02-05 08:42:08"),
        ResetType.DAILY,
        {},
    )
    assert result == _dt("2026-02-06 00:00:00")


def test_next_run_at_interval_uses_config_seconds():
    result = task_schedule.compute_next_run_at(
        _dt("2026-02-03 17:23:00"),
        ResetType.INTERVAL,
        {"interval_seconds": 259200},
    )
    assert result == _dt("2026-02-06 17:23:00")


def test_should_reset_task_prefers_schedule_anchor_at_over_last_completed_at():
    instance = SimpleNamespace(
        status=TaskStatus.COMPLETED.value,
        last_completed_at=_dt("2026-02-01 08:00:00"),
        schedule_anchor_at=_dt("2026-02-04 09:00:00"),
        next_run_at=_dt("2026-02-06 00:00:00"),
    )

    result = task_schedule.should_reset_task(
        instance,
        ResetType.DAILY,
        {},
        now=_dt("2026-02-05 12:00:00"),
    )

    assert result is True


def test_should_not_reset_task_when_schedule_anchor_at_not_due():
    instance = SimpleNamespace(
        status=TaskStatus.COMPLETED.value,
        last_completed_at=None,
        schedule_anchor_at=_dt("2026-02-05 09:00:00"),
        next_run_at=_dt("2026-02-05 00:00:00"),
    )

    result = task_schedule.should_reset_task(
        instance,
        ResetType.DAILY,
        {},
        now=_dt("2026-02-05 12:00:00"),
    )

    assert result is False
