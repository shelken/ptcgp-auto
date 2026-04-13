# -*- coding: utf-8 -*-
"""E2E harness 快照字段测试。"""

from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace

import pytest

import ptcgp_auto_v2.tests.e2e.harness as harness_module
from ptcgp_auto_v2.tests.e2e.harness import SchedulerHarness


class _FakeTaskRepo:
    def get_by_account_and_type(self, account_id: int, task_type: str):
        del account_id, task_type
        return None


class _FakeRepositoryFactory:
    def __init__(self, session):
        del session

    def task_instances(self):
        return _FakeTaskRepo()


class _FakeDevicePool:
    def get_status_summary(self):
        return {"idle": 1}


class _FakeScheduler:
    def __init__(self):
        self.device_pool = _FakeDevicePool()

    def _snapshot_active_account_ids(self):
        return []


@contextmanager
def _fake_session_scope():
    yield object()


def _patch_snapshot_runtime_dependencies(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(harness_module, "session_scope", _fake_session_scope)
    monkeypatch.setattr(harness_module, "RepositoryFactory", _FakeRepositoryFactory)


@pytest.mark.parametrize("supervisor_attr", ["runtime_supervisor", "_runtime_supervisor"])
def test_snapshot_runtime_reads_device_process_phase_from_supervisor(
    monkeypatch: pytest.MonkeyPatch,
    supervisor_attr: str,
):
    _patch_snapshot_runtime_dependencies(monkeypatch)
    harness = SchedulerHarness(
        db_path=Path("/tmp/e2e_snapshot.db"),
        device_addresses=["127.0.0.1:5555"],
    )
    scheduler = _FakeScheduler()
    setattr(
        scheduler,
        supervisor_attr,
        SimpleNamespace(
            get_device_phase=lambda _address: "recovering",
            active_run_account_ids=lambda: set(),
        ),
    )

    snapshot = harness.snapshot_runtime(1, "claim_gifts", scheduler=scheduler)

    assert snapshot["device_process_phase"] == "recovering"


def test_snapshot_runtime_device_process_phase_defaults_none_without_supervisor(
    monkeypatch: pytest.MonkeyPatch,
):
    _patch_snapshot_runtime_dependencies(monkeypatch)
    harness = SchedulerHarness(
        db_path=Path("/tmp/e2e_snapshot.db"),
        device_addresses=["127.0.0.1:5555"],
    )
    scheduler = _FakeScheduler()

    snapshot = harness.snapshot_runtime(1, "claim_gifts", scheduler=scheduler)

    assert snapshot["device_process_phase"] is None
