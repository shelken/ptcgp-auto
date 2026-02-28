# -*- coding: utf-8 -*-
"""元数据同步快照仓储。"""

from __future__ import annotations

from datetime import datetime

from sqlmodel import Session, col, select

from ptcgp_auto_v2.db.engine import get_engine
from ptcgp_auto_v2.db.models import MetadataSyncSnapshot


class MetadataSyncSnapshotRepository:
    """元数据同步快照数据访问层。"""

    def create_snapshot(
        self,
        snapshot_id: str,
        scope_level: str,
        scope_value: str | None,
        source: str,
        mode: str,
        payload_json: str,
        summary_json: str,
        expires_at: datetime,
    ) -> MetadataSyncSnapshot:
        """创建预览快照。"""
        row = MetadataSyncSnapshot(
            snapshot_id=snapshot_id,
            scope_level=scope_level,
            scope_value=scope_value,
            source=source,
            mode=mode,
            payload_json=payload_json,
            summary_json=summary_json,
            expires_at=expires_at,
            status="previewed",
        )
        with Session(get_engine()) as session:
            session.add(row)
            session.commit()
            session.refresh(row)
            return row

    def get_snapshot(
        self,
        snapshot_id: str,
        include_expired: bool = False,
        now: datetime | None = None,
    ) -> MetadataSyncSnapshot | None:
        """根据 snapshot_id 获取最新快照。"""
        current_time = now or datetime.now()
        with Session(get_engine()) as session:
            statement = (
                select(MetadataSyncSnapshot)
                .where(MetadataSyncSnapshot.snapshot_id == snapshot_id)
                .order_by(col(MetadataSyncSnapshot.created_at).desc())
                .limit(1)
            )
            row = session.exec(statement).first()
            if not row:
                return None
            if include_expired:
                return row
            if row.status == "expired":
                return None
            if row.expires_at <= current_time:
                return None
            return row

    def mark_executed(
        self,
        snapshot_id: str,
        now: datetime | None = None,
    ) -> bool:
        """标记快照已执行。"""
        current_time = now or datetime.now()
        with Session(get_engine()) as session:
            statement = (
                select(MetadataSyncSnapshot)
                .where(MetadataSyncSnapshot.snapshot_id == snapshot_id)
                .order_by(col(MetadataSyncSnapshot.created_at).desc())
                .limit(1)
            )
            row = session.exec(statement).first()
            if not row:
                return False
            row.status = "executed"
            row.executed_at = current_time
            row.updated_at = current_time
            session.add(row)
            session.commit()
            return True

    def mark_expired(self, now: datetime | None = None) -> int:
        """将过期且未执行的快照批量标记为 expired。"""
        current_time = now or datetime.now()
        with Session(get_engine()) as session:
            statement = select(MetadataSyncSnapshot).where(
                MetadataSyncSnapshot.status == "previewed",
                MetadataSyncSnapshot.expires_at <= current_time,
            )
            rows = list(session.exec(statement).all())
            for row in rows:
                row.status = "expired"
                row.updated_at = current_time
                session.add(row)
            session.commit()
            return len(rows)

    def list_recent_snapshots(self, limit: int = 20) -> list[MetadataSyncSnapshot]:
        """按创建时间倒序返回最近快照。"""
        with Session(get_engine()) as session:
            statement = (
                select(MetadataSyncSnapshot)
                .order_by(col(MetadataSyncSnapshot.created_at).desc())
                .limit(limit)
            )
            return list(session.exec(statement).all())
