# -*- coding: utf-8 -*-
"""
任务调度统一逻辑

用于调度器与 Web 展示共享计算规则。
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, Optional

from ptcgp_auto_v2.core.task_base import ResetType, TaskStatus


def _normalize_reset_type(value: Any) -> Optional[ResetType]:
    if isinstance(value, ResetType):
        return value
    if isinstance(value, str):
        try:
            return ResetType(value)
        except ValueError:
            return None
    return None


def get_effective_reset_type(
    task_class: Any, config: dict[str, Any] | None
) -> ResetType:
    if config is None:
        config = {}

    configured = _normalize_reset_type(config.get("reset_type"))
    if configured is not None:
        return configured

    return task_class.reset_type


def get_interval_seconds(
    config: dict[str, Any] | None,
    default_seconds: int = 3600,
) -> int:
    if config is None:
        return default_seconds

    interval = config.get("interval_seconds", default_seconds)
    if isinstance(interval, str) and interval.isdigit():
        return int(interval)
    if isinstance(interval, int):
        return interval
    return default_seconds


def should_reset_task(
    instance: Any,
    reset_type: ResetType,
    config: dict[str, Any] | None = None,
    now: datetime | None = None,
) -> bool:
    if config is None:
        config = {}

    if instance.status != TaskStatus.COMPLETED.value:
        return False

    if not instance.last_completed_at:
        return False

    if now is None:
        now = datetime.now()

    last_completed = instance.last_completed_at

    if reset_type == ResetType.DAILY:
        return last_completed.date() < now.date()

    if reset_type == ResetType.WEEKLY:
        last_week = last_completed.isocalendar()[1]
        current_week = now.isocalendar()[1]
        return last_week != current_week or last_completed.year != now.year

    if reset_type == ResetType.ONCE:
        return False

    if reset_type == ResetType.INTERVAL:
        interval = get_interval_seconds(config)
        return (now - last_completed).total_seconds() >= interval

    return False


def _next_daily_reset(last_completed: datetime) -> datetime:
    next_day = (last_completed + timedelta(days=1)).date()
    return datetime.combine(next_day, datetime.min.time())


def _next_weekly_reset(last_completed: datetime) -> datetime:
    weekday = last_completed.weekday()
    days_until_monday = (7 - weekday) % 7
    if days_until_monday == 0:
        days_until_monday = 7
    next_monday = (last_completed + timedelta(days=days_until_monday)).date()
    return datetime.combine(next_monday, datetime.min.time())


def compute_next_run_at(
    last_completed: datetime | None,
    reset_type: ResetType,
    config: dict[str, Any] | None = None,
) -> datetime | None:
    if last_completed is None:
        return None

    if reset_type == ResetType.DAILY:
        return _next_daily_reset(last_completed)

    if reset_type == ResetType.WEEKLY:
        return _next_weekly_reset(last_completed)

    if reset_type == ResetType.INTERVAL:
        interval = get_interval_seconds(config)
        return last_completed + timedelta(seconds=interval)

    return None
