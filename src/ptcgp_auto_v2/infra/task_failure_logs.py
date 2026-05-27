# -*- coding: utf-8 -*-
"""任务失败日志切片持久化。"""

from __future__ import annotations

import json
import re
import threading
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from loguru import logger

_RETENTION_DAYS = 3
_SAFE_NAME_PATTERN = re.compile(r"[^A-Za-z0-9_.-]+")


def _safe_filename_part(value: object) -> str:
    """把业务字段压成文件名安全片段。"""
    text = str(value).strip()
    if not text:
        return "unknown"
    normalized = _SAFE_NAME_PATTERN.sub("-", text).strip("-._")
    return normalized or "unknown"


@dataclass
class TaskFailureLogContext:
    """捕获单次任务日志，失败时写入 `data/logs` JSONL。"""

    log_dir: Path
    started_at: datetime
    account_id: int | None
    account_name: str
    task_type: str
    task_instance_id: int | None
    level: str = "TRACE"

    def __post_init__(self) -> None:
        self._events: list[dict[str, Any]] = []
        self._sink_id: int | None = None
        self._thread_id: int | None = None

    def __enter__(self) -> "TaskFailureLogContext":
        self._thread_id = threading.get_ident()
        self._sink_id = logger.add(
            self._append_event,
            level=self.level,
            enqueue=False,
            catch=False,
        )
        return self

    def __exit__(self, _exc_type, _exc, _tb) -> None:
        if self._sink_id is not None:
            logger.remove(self._sink_id)
            self._sink_id = None

    def persist_failure(self, reason: str) -> Path:
        """把当前捕获日志写入失败切片 JSONL 文件。"""
        cleanup_old_task_failure_logs(log_dir=self.log_dir)
        self.log_dir.mkdir(parents=True, exist_ok=True)
        path = self.log_dir / self._build_filename()
        summary = {
            "event": "task_failure_summary",
            "task_started_at": self.started_at.isoformat(),
            "account_id": self.account_id,
            "account_name": self.account_name,
            "task_type": self.task_type,
            "task_instance_id": self.task_instance_id,
            "failure_reason": reason,
        }
        rows = [summary, *self._events]
        path.write_text(
            "\n".join(json.dumps(row, ensure_ascii=False) for row in rows) + "\n",
            encoding="utf-8",
        )
        return path

    def _append_event(self, message) -> None:
        """把 loguru record 转成结构化事件。"""
        from ptcgp_auto_v2.utils.logger import get_context_snapshot

        record = message.record
        if self._thread_id is not None and record["thread"].id != self._thread_id:
            return
        extra = record["extra"]
        context = get_context_snapshot()
        self._events.append(
            {
                "event": "log",
                "time": record["time"].isoformat(),
                "level": record["level"].name,
                "logger": record["name"],
                "message": record["message"],
                "device": extra.get("device", context["device"]),
                "account": extra.get("nickname", context["nickname"]),
                "task": extra.get("task", context["task"]),
                "thread": record["thread"].name,
                "process": record["process"].name,
            }
        )

    def _build_filename(self) -> str:
        timestamp = self.started_at.strftime("%Y%m%d-%H%M%S")
        account_id = _safe_filename_part(self.account_id)
        account_name = _safe_filename_part(self.account_name)
        task_type = _safe_filename_part(self.task_type)
        task_instance_id = _safe_filename_part(self.task_instance_id)
        return (
            f"{timestamp}_account-{account_id}-{account_name}_"
            f"task-{task_type}_instance-{task_instance_id}_failed.jsonl"
        )


def cleanup_old_task_failure_logs(
    *,
    log_dir: Path,
    now: datetime | None = None,
    retention_days: int = _RETENTION_DAYS,
) -> int:
    """删除保留期外的任务失败日志，返回删除数量。"""
    if not log_dir.exists():
        return 0

    reference_time = now or datetime.now()
    cutoff = reference_time - timedelta(days=retention_days)
    removed = 0
    for path in log_dir.glob("*.jsonl"):
        modified_at = datetime.fromtimestamp(path.stat().st_mtime)
        if modified_at >= cutoff:
            continue
        path.unlink()
        removed += 1
    return removed
