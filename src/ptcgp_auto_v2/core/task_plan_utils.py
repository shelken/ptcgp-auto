from __future__ import annotations

from datetime import datetime
from typing import Any

from ptcgp_auto_v2.core.task_base import TaskRegistry, ResetType
from ptcgp_auto_v2.core.task_schedule import (
    compute_next_run_at,
    get_effective_reset_type,
    get_interval_seconds,
)


def build_account_plan_cache(account: Any) -> dict:
    """构建账号计划配置缓存。"""
    associations = [
        assoc
        for assoc in (account.task_plan_associations or [])
        if assoc.is_active and assoc.task_plan
    ]
    associations.sort(key=lambda item: (-item.priority, item.task_plan_id))

    merged_config: dict[str, dict] = {}
    plan_source: dict[str, dict] = {}

    for assoc in reversed(associations):
        plan = assoc.task_plan
        if not plan:
            continue
        plan_config = plan.config_dict
        for task_type, config in plan_config.items():
            if task_type in merged_config:
                merged_config[task_type].update(config)
            else:
                merged_config[task_type] = config.copy()

    for assoc in associations:
        plan = assoc.task_plan
        if not plan:
            continue
        for task_type in plan.task_types_list:
            if task_type not in plan_source:
                plan_source[task_type] = {
                    "name": plan.name,
                    "priority": assoc.priority,
                }

    return {"config": merged_config, "source": plan_source}


def resolve_task_reset_info(
    task_type: str,
    account_cache: dict,
    fallback_reset_type: str,
) -> tuple[ResetType, dict, int | None, dict | None]:
    """解析任务重置规则与计划来源。"""
    config = account_cache["config"].get(task_type, {})
    task_class = TaskRegistry.get_or_none(task_type)
    if task_class:
        effective_reset_type = get_effective_reset_type(task_class, config)
    else:
        try:
            effective_reset_type = ResetType(fallback_reset_type)
        except ValueError:
            effective_reset_type = ResetType.DAILY

    interval_seconds = None
    if effective_reset_type == ResetType.INTERVAL:
        interval_seconds = get_interval_seconds(config)

    plan_source = account_cache["source"].get(task_type)
    return effective_reset_type, config, interval_seconds, plan_source


def compute_next_run_for_instance(
    instance: Any, account_cache: dict
) -> tuple[datetime | None, ResetType, int | None, dict | None]:
    """根据任务实例与计划配置计算下次运行时间。"""
    effective_reset_type, config, interval_seconds, plan_source = (
        resolve_task_reset_info(
            instance.task_type,
            account_cache,
            instance.reset_type,
        )
    )
    schedule_anchor_at = getattr(instance, "schedule_anchor_at", None)
    if schedule_anchor_at is None:
        schedule_anchor_at = instance.last_completed_at

    next_run_at = compute_next_run_at(
        schedule_anchor_at,
        effective_reset_type,
        config,
    )
    return next_run_at, effective_reset_type, interval_seconds, plan_source
