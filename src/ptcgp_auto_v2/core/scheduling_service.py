# -*- coding: utf-8 -*-
"""调度规则统一服务。

集中维护调度器、仓储与 Web 共享的任务调度口径，避免规则分散导致行为漂移。
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Optional, cast

from sqlalchemy import and_, or_
from sqlmodel import Session, case, col, func

from ptcgp_auto_v2.core.task_status import TaskStatus
from ptcgp_auto_v2.db.models import TaskInstance
from ptcgp_auto_v2.utils.game_time import get_game_day_window

# 任务列表排序字段常量（Web 与仓储层共享）
TASK_SORT_BY_DISPATCH_PRIORITY = "dispatch_priority"
TASK_SORT_BY_LAST_COMPLETED = "last_completed_at"
TASK_SORT_BY_LAST_DURATION = "last_duration_seconds"
TASK_SORT_BY_NEXT_RUN = "next_run_at"

# 重置类型字面量常量（避免调度服务依赖任务基类，降低导入耦合）
RESET_TYPE_DAILY = "daily"
RESET_TYPE_WEEKLY = "weekly"
RESET_TYPE_ONCE = "once"
RESET_TYPE_INTERVAL = "interval"
ALLOWED_RESET_TYPES = {
    RESET_TYPE_DAILY,
    RESET_TYPE_WEEKLY,
    RESET_TYPE_ONCE,
    RESET_TYPE_INTERVAL,
}

DISPATCH_CATEGORY_ONCE = "once"
DISPATCH_CATEGORY_IMMEDIATE = "immediate"
DISPATCH_CATEGORY_SCHEDULED = "scheduled"
PREREQUISITE_TASK_TYPE_FETCH_ACCOUNT_INFO = "fetch_account_info"


@dataclass(frozen=True)
class AccountSchedulingContext:
    """账号级调度上下文。"""

    aggregated_config: dict[str, dict[str, Any]]
    plan_source: dict[str, dict[str, Any]]
    task_order: list[str]


@dataclass(frozen=True)
class AccountDispatchPlan:
    """账号当前批次的真实调度顺序。"""

    ordered_tasks: tuple[Any, ...]
    missing_prerequisite_task_type: str | None


@dataclass(frozen=True)
class TaskSchedulingSummary:
    """任务统一调度摘要。"""

    effective_reset_type: str
    next_run_at: datetime | None
    interval_seconds: int | None
    plan_name: str | None
    plan_priority: int | None
    dispatch_category: str
    dispatch_label_key: str
    dispatch_css_class: str
    dispatch_rank: int | None
    dispatch_rank_total: int | None


def _normalize_reset_type(value: Any) -> Optional[str]:
    """将输入值标准化为重置类型字符串。"""
    if isinstance(value, str) and value in ALLOWED_RESET_TYPES:
        return value
    enum_value = getattr(value, "value", None)
    if isinstance(enum_value, str) and enum_value in ALLOWED_RESET_TYPES:
        return enum_value
    if isinstance(value, str):
        return None
    return None


def get_effective_reset_type(task_class: Any, config: dict[str, Any] | None) -> str:
    """解析任务的生效重置类型（配置优先，默认兜底）。"""
    if config is None:
        config = {}

    configured = _normalize_reset_type(config.get("reset_type"))
    if configured is not None:
        return configured
    task_default = _normalize_reset_type(getattr(task_class, "reset_type", None))
    if task_default is not None:
        return task_default
    return RESET_TYPE_DAILY


def get_interval_seconds(
    config: dict[str, Any] | None,
    default_seconds: int = 3600,
) -> int:
    """解析 interval 重置的秒数配置。"""
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
    reset_type: str,
    config: dict[str, Any] | None = None,
    now: datetime | None = None,
) -> bool:
    """判断任务实例是否应从 completed 重置为 pending。"""
    if config is None:
        config = {}

    if instance.status != TaskStatus.COMPLETED.value:
        return False

    if now is None:
        now = datetime.now()

    schedule_anchor_at = getattr(instance, "schedule_anchor_at", None)
    if schedule_anchor_at is None:
        schedule_anchor_at = instance.last_completed_at
    if schedule_anchor_at is None:
        return False

    if reset_type == RESET_TYPE_DAILY:
        last_window_start, _ = get_game_day_window(schedule_anchor_at)
        current_window_start, _ = get_game_day_window(now)
        return last_window_start < current_window_start
    if reset_type == RESET_TYPE_WEEKLY:
        last_week = schedule_anchor_at.isocalendar()[1]
        current_week = now.isocalendar()[1]
        return last_week != current_week or schedule_anchor_at.year != now.year
    if reset_type == RESET_TYPE_ONCE:
        return False
    if reset_type == RESET_TYPE_INTERVAL:
        interval = get_interval_seconds(config)
        return (now - schedule_anchor_at).total_seconds() >= interval
    return False


def _next_daily_reset(last_completed: datetime) -> datetime:
    """计算每日任务下一次运行时间（按游戏刷新时刻）。"""
    _, next_reset_at = get_game_day_window(last_completed)
    return next_reset_at


def _next_weekly_reset(last_completed: datetime) -> datetime:
    """计算每周任务下一次运行时间（下个周一零点）。"""
    weekday = last_completed.weekday()
    days_until_monday = (7 - weekday) % 7
    if days_until_monday == 0:
        days_until_monday = 7
    next_monday = (last_completed + timedelta(days=days_until_monday)).date()
    return datetime.combine(next_monday, datetime.min.time())


def compute_next_run_at(
    last_completed: datetime | None,
    reset_type: str,
    config: dict[str, Any] | None = None,
) -> datetime | None:
    """按重置规则计算下一次运行时间。"""
    if last_completed is None:
        return None

    if reset_type == RESET_TYPE_DAILY:
        return _next_daily_reset(last_completed)
    if reset_type == RESET_TYPE_WEEKLY:
        return _next_weekly_reset(last_completed)
    if reset_type == RESET_TYPE_INTERVAL:
        interval = get_interval_seconds(config)
        return last_completed + timedelta(seconds=interval)
    return None


def normalize_task_sort(sort_by: str | None, sort_order: str | None) -> tuple[str, str]:
    """标准化任务排序参数。"""
    allowed_sort_by = {
        TASK_SORT_BY_DISPATCH_PRIORITY,
        TASK_SORT_BY_LAST_COMPLETED,
        TASK_SORT_BY_LAST_DURATION,
        TASK_SORT_BY_NEXT_RUN,
    }
    normalized_sort_by = (
        sort_by if sort_by in allowed_sort_by else TASK_SORT_BY_DISPATCH_PRIORITY
    )

    if normalized_sort_by == TASK_SORT_BY_DISPATCH_PRIORITY:
        normalized_sort_order = "asc"
    elif sort_order in {"asc", "desc"}:
        normalized_sort_order = sort_order
    else:
        normalized_sort_order = "desc"
    return normalized_sort_by, normalized_sort_order


def build_task_instance_order_by(sort_by: str, sort_order: str) -> list:
    """构建 TaskInstance 的统一排序表达式。"""
    normalized_sort_by, normalized_sort_order = normalize_task_sort(sort_by, sort_order)

    next_run_col = col(cast(Any, TaskInstance.next_run_at))
    last_completed_col = col(cast(Any, TaskInstance.last_completed_at))
    schedule_anchor_col = func.coalesce(
        col(cast(Any, TaskInstance.schedule_anchor_at)),
        last_completed_col,
    )
    last_duration_col = col(cast(Any, TaskInstance.last_duration_seconds))
    task_id_col = col(cast(Any, TaskInstance.id))

    if normalized_sort_by == TASK_SORT_BY_DISPATCH_PRIORITY:
        reset_priority = case((TaskInstance.reset_type == RESET_TYPE_ONCE, 0), else_=1)
        return [
            reset_priority.asc(),
            next_run_col.asc().nulls_first(),
            schedule_anchor_col.asc().nulls_first(),
            task_id_col.asc(),
        ]

    if normalized_sort_by == TASK_SORT_BY_NEXT_RUN:
        once_priority = case((TaskInstance.reset_type == RESET_TYPE_ONCE, 1), else_=0)
        if normalized_sort_order == "asc":
            return [once_priority.asc(), next_run_col.asc().nulls_first()]
        return [once_priority.asc(), next_run_col.desc().nulls_first()]

    if normalized_sort_by == TASK_SORT_BY_LAST_DURATION:
        once_priority = case((TaskInstance.reset_type == RESET_TYPE_ONCE, 1), else_=0)
        if normalized_sort_order == "asc":
            return [once_priority.asc(), last_duration_col.asc().nulls_last()]
        return [once_priority.asc(), last_duration_col.desc().nulls_last()]

    once_priority = case((TaskInstance.reset_type == RESET_TYPE_ONCE, 1), else_=0)
    if normalized_sort_order == "asc":
        return [once_priority.asc(), last_completed_col.asc().nulls_first()]
    return [once_priority.asc(), last_completed_col.desc().nulls_first()]


def build_due_pending_condition(now: datetime):
    """构建 pending 且已到可执行时间的 SQL 条件。"""
    next_run_at_col = col(cast(Any, TaskInstance.next_run_at))
    return and_(
        col(TaskInstance.status) == TaskStatus.PENDING.value,
        or_(next_run_at_col.is_(None), next_run_at_col <= now),
    )


def _get_active_plan_associations(account: Any) -> list[Any]:
    """获取按统一口径排序后的启用计划关联。"""
    associations = [
        assoc
        for assoc in (account.task_plan_associations or [])
        if assoc.is_active and assoc.task_plan
    ]
    associations.sort(key=lambda item: (-item.priority, item.task_plan_id))
    return associations


def build_account_scheduling_context(account: Any) -> AccountSchedulingContext:
    """构建账号级统一调度上下文。"""
    associations = _get_active_plan_associations(account)
    merged_config: dict[str, dict[str, Any]] = {}
    plan_source: dict[str, dict[str, Any]] = {}
    task_order: list[str] = []

    for assoc in associations:
        plan = assoc.task_plan
        if plan is None:
            continue
        for task_type in plan.task_types_list:
            if task_type not in task_order:
                task_order.append(task_type)
            if task_type not in plan_source:
                plan_source[task_type] = {
                    "name": plan.name,
                    "priority": assoc.priority,
                    "task_plan_id": assoc.task_plan_id,
                }

    for assoc in reversed(associations):
        plan = assoc.task_plan
        if plan is None:
            continue
        plan_config = plan.config_dict
        for task_type in plan.task_types_list:
            config = plan_config.get(task_type, {})
            if task_type in merged_config:
                merged_config[task_type].update(config)
            else:
                merged_config[task_type] = config.copy()

    return AccountSchedulingContext(
        aggregated_config=merged_config,
        plan_source=plan_source,
        task_order=task_order,
    )


def order_account_tasks(
    context: AccountSchedulingContext, tasks: list[Any]
) -> list[Any]:
    """按账号调度上下文对任务排序。"""
    if not context.task_order:
        return sorted(
            tasks,
            key=lambda task: getattr(task, "created_at", None) or datetime.min,
        )

    plan_order = {task_type: idx for idx, task_type in enumerate(context.task_order)}
    return sorted(
        tasks,
        key=lambda task: (
            plan_order.get(getattr(task, "task_type"), len(plan_order)),
            getattr(task, "created_at", None) or datetime.min,
        ),
    )


def find_incomplete_init_task(tasks: list[Any]) -> Any | None:
    """查找当前批次中未完成的 init_account 任务。"""
    for task in tasks:
        if getattr(task, "task_type", None) != "init_account":
            continue
        if getattr(task, "status", None) in (
            TaskStatus.COMPLETED.value,
            TaskStatus.SKIPPED.value,
        ):
            continue
        return task
    return None


def resolve_account_dispatch_plan(
    account: Any,
    tasks: list[Any],
    context: AccountSchedulingContext | None = None,
) -> AccountDispatchPlan:
    """解析账号当前批次的真实调度顺序与缺失前置任务。"""
    init_task = find_incomplete_init_task(tasks)
    if init_task is not None:
        ordered_tasks = (init_task,)
    else:
        resolved_context = context or build_account_scheduling_context(account)
        ordered_tasks = tuple(order_account_tasks(resolved_context, tasks))

    if not should_insert_fetch_account_info(account, list(ordered_tasks)):
        return AccountDispatchPlan(
            ordered_tasks=ordered_tasks,
            missing_prerequisite_task_type=None,
        )
    return AccountDispatchPlan(
        ordered_tasks=ordered_tasks,
        missing_prerequisite_task_type=PREREQUISITE_TASK_TYPE_FETCH_ACCOUNT_INFO,
    )


def should_insert_fetch_account_info(account: Any, tasks: list[Any]) -> bool:
    """判断当前任务批次是否需要插入账号信息前置任务。"""
    from ptcgp_auto_v2.tasks.fetch_account_info import FetchAccountInfoTask

    needs_fetch = getattr(FetchAccountInfoTask, "needs_fetch", None)
    if needs_fetch is None:
        raise RuntimeError("FetchAccountInfoTask.needs_fetch 未定义")
    if any(
        getattr(task, "task_type", None) == PREREQUISITE_TASK_TYPE_FETCH_ACCOUNT_INFO
        for task in tasks
    ):
        return False
    return bool(needs_fetch(account, tasks))


def build_account_plan_cache(account: Any) -> dict:
    """构建账号计划配置缓存。"""
    context = build_account_scheduling_context(account)
    return {
        "config": context.aggregated_config,
        "source": context.plan_source,
        "task_order": context.task_order,
    }


def resolve_task_reset_info(
    task_type: str,
    account_cache: dict,
    fallback_reset_type: str,
) -> tuple[str, dict[str, Any], int | None, dict[str, Any] | None]:
    """解析任务重置规则、interval 与计划来源。"""
    from ptcgp_auto_v2.core.task_base import TaskRegistry

    config = account_cache["config"].get(task_type, {})
    task_class = TaskRegistry.get_or_none(task_type)
    if task_class:
        effective_reset_type = get_effective_reset_type(task_class, config)
    else:
        normalized_fallback = _normalize_reset_type(fallback_reset_type)
        if normalized_fallback is not None:
            effective_reset_type = normalized_fallback
        else:
            effective_reset_type = RESET_TYPE_DAILY

    interval_seconds = None
    if effective_reset_type == RESET_TYPE_INTERVAL:
        interval_seconds = get_interval_seconds(config)

    plan_source = account_cache["source"].get(task_type)
    return effective_reset_type, config, interval_seconds, plan_source


def compute_next_run_for_instance(
    instance: Any,
    account_cache: dict,
) -> tuple[datetime | None, str, int | None, dict[str, Any] | None]:
    """根据任务实例与计划配置计算 next_run_at。"""
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


def get_dispatch_category(
    effective_reset_type: str,
    next_run_at: datetime | None,
    now: datetime | None = None,
) -> str:
    """统一判定任务调度类别。"""
    if effective_reset_type == RESET_TYPE_ONCE:
        return DISPATCH_CATEGORY_ONCE
    if next_run_at is None:
        return DISPATCH_CATEGORY_IMMEDIATE
    if now is None:
        now = datetime.now()
    if next_run_at <= now:
        return DISPATCH_CATEGORY_IMMEDIATE
    return DISPATCH_CATEGORY_SCHEDULED


def _is_same_task_instance(left: Any, right: Any) -> bool:
    """按任务实例 ID 比较两个对象是否指向同一任务。"""
    left_id = getattr(left, "id", None)
    right_id = getattr(right, "id", None)
    if left_id is not None and right_id is not None:
        return left_id == right_id
    return left is right


def build_task_scheduling_summary(
    instance: Any,
    account_cache: dict,
    now: datetime | None = None,
    dispatch_plan: AccountDispatchPlan | None = None,
) -> TaskSchedulingSummary:
    """构建任务统一调度摘要。"""
    next_run_at, effective_reset_type, interval_seconds, plan_source = (
        compute_next_run_for_instance(
            instance,
            account_cache,
        )
    )
    dispatch_rank = None
    dispatch_rank_total = None
    in_current_dispatch_batch = dispatch_plan is None
    if dispatch_plan is not None:
        ordered_tasks = list(dispatch_plan.ordered_tasks)
        dispatch_rank_total = len(ordered_tasks)
        prerequisite_task_type = dispatch_plan.missing_prerequisite_task_type
        if prerequisite_task_type is not None:
            dispatch_rank_total += 1
            if getattr(instance, "task_type", None) == prerequisite_task_type:
                dispatch_rank = 1
            else:
                for index, task in enumerate(ordered_tasks, start=2):
                    if _is_same_task_instance(task, instance):
                        dispatch_rank = index
                        break
        else:
            for index, task in enumerate(ordered_tasks, start=1):
                if _is_same_task_instance(task, instance):
                    dispatch_rank = index
                    break
        in_current_dispatch_batch = dispatch_rank is not None

    if in_current_dispatch_batch:
        dispatch_category = get_dispatch_category(
            effective_reset_type,
            next_run_at,
            now,
        )
    else:
        # 未进入当前批次（如非 pending/未到执行窗口/被 init_account 阻断）统一按时间显示
        dispatch_category = DISPATCH_CATEGORY_SCHEDULED

    dispatch_label_key = {
        DISPATCH_CATEGORY_ONCE: "label_dispatch_once_first",
        DISPATCH_CATEGORY_IMMEDIATE: "label_dispatch_immediate",
        DISPATCH_CATEGORY_SCHEDULED: "label_dispatch_scheduled",
    }[dispatch_category]
    dispatch_css_class = (
        "text-xs text-muted"
        if dispatch_category == DISPATCH_CATEGORY_SCHEDULED
        else "brutal-tag text-xs"
    )

    return TaskSchedulingSummary(
        effective_reset_type=effective_reset_type,
        next_run_at=next_run_at,
        interval_seconds=interval_seconds,
        plan_name=plan_source["name"] if plan_source else None,
        plan_priority=plan_source["priority"] if plan_source else None,
        dispatch_category=dispatch_category,
        dispatch_label_key=dispatch_label_key,
        dispatch_css_class=dispatch_css_class,
        dispatch_rank=dispatch_rank,
        dispatch_rank_total=dispatch_rank_total,
    )


def recompute_and_sync_account_scheduling(
    *,
    session: Session,
    account: Any | None = None,
    account_id: int | None = None,
    task_types: list[str] | None = None,
) -> int:
    """按账号重算并回写任务调度字段。"""
    from ptcgp_auto_v2.db.repositories import AccountRepository, TaskInstanceRepository

    if account is None:
        if account_id is None:
            raise ValueError("account 与 account_id 不能同时为空")
        account = AccountRepository(session).get_by_id(account_id)
    if account is None or account.id is None:
        return 0

    repo = TaskInstanceRepository(session)
    instances = repo.list_by_account(account.id)
    if task_types is not None:
        task_type_set = set(task_types)
        instances = [item for item in instances if item.task_type in task_type_set]
    if not instances:
        return 0

    account_cache = build_account_plan_cache(account)
    for instance in instances:
        next_run_at, effective_reset_type, _, _ = compute_next_run_for_instance(
            instance,
            account_cache,
        )
        instance.reset_type = effective_reset_type
        instance.next_run_at = next_run_at

    return repo.update_scheduling_fields(instances)
