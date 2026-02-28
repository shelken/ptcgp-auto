# -*- coding: utf-8 -*-
"""MetadataSyncSnapshotRepository 单元测试。"""

from __future__ import annotations

from datetime import datetime, timedelta

from ptcgp_auto_v2.db.repositories.metadata_sync_snapshot_repository import (
    MetadataSyncSnapshotRepository,
)


def test_create_and_get_snapshot_success() -> None:
    """应能创建快照并按 snapshot_id 读取。"""
    repo = MetadataSyncSnapshotRepository()
    expires_at = datetime.now() + timedelta(minutes=10)

    created = repo.create_snapshot(
        snapshot_id="snp-001",
        scope_level="all",
        scope_value=None,
        source="full",
        mode="supplement",
        payload_json='{"rows":1}',
        summary_json='{"set_new":1}',
        expires_at=expires_at,
    )

    fetched = repo.get_snapshot("snp-001")

    assert created.id is not None
    assert fetched is not None
    assert fetched.snapshot_id == "snp-001"
    assert fetched.status == "previewed"
    assert fetched.payload_json == '{"rows":1}'


def test_get_snapshot_returns_none_when_expired() -> None:
    """过期快照在默认查询下应不可见。"""
    repo = MetadataSyncSnapshotRepository()
    expired_time = datetime.now() - timedelta(minutes=1)

    repo.create_snapshot(
        snapshot_id="snp-expired",
        scope_level="set",
        scope_value="A1",
        source="flibustier",
        mode="force",
        payload_json="{}",
        summary_json="{}",
        expires_at=expired_time,
    )

    assert repo.get_snapshot("snp-expired") is None
    assert repo.get_snapshot("snp-expired", include_expired=True) is not None


def test_mark_executed_updates_status_and_time() -> None:
    """执行后应更新状态为 executed 并记录 executed_at。"""
    repo = MetadataSyncSnapshotRepository()
    repo.create_snapshot(
        snapshot_id="snp-exec",
        scope_level="pack",
        scope_value="Pikachu",
        source="52poke",
        mode="supplement",
        payload_json="{}",
        summary_json="{}",
        expires_at=datetime.now() + timedelta(minutes=5),
    )

    ok = repo.mark_executed("snp-exec")
    row = repo.get_snapshot("snp-exec", include_expired=True)

    assert ok is True
    assert row is not None
    assert row.status == "executed"
    assert row.executed_at is not None


def test_mark_expired_only_affects_previewed_rows() -> None:
    """批量过期仅应影响 previewed 且已过期的快照。"""
    repo = MetadataSyncSnapshotRepository()
    now = datetime.now()

    repo.create_snapshot(
        snapshot_id="snp-old-preview",
        scope_level="all",
        scope_value=None,
        source="full",
        mode="supplement",
        payload_json="{}",
        summary_json="{}",
        expires_at=now - timedelta(minutes=2),
    )
    repo.create_snapshot(
        snapshot_id="snp-future-preview",
        scope_level="all",
        scope_value=None,
        source="full",
        mode="supplement",
        payload_json="{}",
        summary_json="{}",
        expires_at=now + timedelta(minutes=10),
    )
    repo.create_snapshot(
        snapshot_id="snp-old-executed",
        scope_level="all",
        scope_value=None,
        source="full",
        mode="supplement",
        payload_json="{}",
        summary_json="{}",
        expires_at=now - timedelta(minutes=5),
    )
    repo.mark_executed("snp-old-executed")

    affected = repo.mark_expired(now=now)

    old_preview = repo.get_snapshot("snp-old-preview", include_expired=True)
    future_preview = repo.get_snapshot("snp-future-preview", include_expired=True)
    old_executed = repo.get_snapshot("snp-old-executed", include_expired=True)

    assert affected == 1
    assert old_preview is not None and old_preview.status == "expired"
    assert future_preview is not None and future_preview.status == "previewed"
    assert old_executed is not None and old_executed.status == "executed"


def test_list_recent_snapshots_returns_latest_first() -> None:
    """最近快照列表应按创建时间倒序返回。"""
    repo = MetadataSyncSnapshotRepository()

    for idx in range(3):
        repo.create_snapshot(
            snapshot_id=f"snp-{idx}",
            scope_level="card",
            scope_value=f"A1-{idx:03d}",
            source="52poke",
            mode="supplement",
            payload_json="{}",
            summary_json="{}",
            expires_at=datetime.now() + timedelta(minutes=20),
        )

    rows = repo.list_recent_snapshots(limit=2)

    assert len(rows) == 2
    assert rows[0].created_at >= rows[1].created_at
