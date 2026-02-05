from typing import Any
from urllib.parse import urlencode

from sqlmodel import Session

from ptcgp_auto_v2.core.task_base import TaskRegistry, ResetType
from ptcgp_auto_v2.core.task_schedule import (
    compute_next_run_at,
    get_effective_reset_type,
    get_interval_seconds,
)
from ptcgp_auto_v2.db.models.account import Account
from ptcgp_auto_v2.db.models.task_instance import TaskInstance
from ptcgp_auto_v2.db.models.account_task_plan import AccountTaskPlan
from ptcgp_auto_v2.web.queries.task_queries import fetch_task_instances
from ptcgp_auto_v2.web.utils.view_helpers import format_datetime_iso


def build_account_plan_cache(account: Account) -> dict:
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


def build_tasks_page_url(
    page: int,
    lang: str,
    status: list[str],
    task_type: list[str],
    account_id: int | None,
) -> str:
    """构建任务分页 URL。"""
    params = [("page", page), ("lang", lang)]
    for item in status:
        params.append(("status", item))
    for item in task_type:
        params.append(("task_type", item))
    if account_id is not None:
        params.append(("account_id", account_id))
    return f"/api/tasks?{urlencode(params)}"


def list_task_status_view(
    session: Session,
    page: int,
    page_size: int,
    status: list[str],
    task_type: list[str],
    account_id: int | None,
) -> tuple[list[dict[str, Any]], bool]:
    """获取任务状态视图数据。"""
    instances, has_more = fetch_task_instances(
        session=session,
        page=page,
        page_size=page_size,
        status=status,
        task_type=task_type,
        account_id=account_id,
    )

    account_cache: dict[int, dict] = {}
    rows: list[dict[str, Any]] = []
    for instance in instances:
        account = instance.account
        if not account or account.id is None:
            continue

        if account.id not in account_cache:
            account_cache[account.id] = build_account_plan_cache(account)

        cache = account_cache[account.id]
        config = cache["config"].get(instance.task_type, {})
        task_class = TaskRegistry.get_or_none(instance.task_type)
        if task_class:
            effective_reset_type = get_effective_reset_type(task_class, config)
        else:
            try:
                effective_reset_type = ResetType(instance.reset_type)
            except ValueError:
                effective_reset_type = ResetType.DAILY

        interval_seconds = None
        if effective_reset_type == ResetType.INTERVAL:
            interval_seconds = get_interval_seconds(config)

        next_run_at = compute_next_run_at(
            instance.last_completed_at,
            effective_reset_type,
            config,
        )

        plan_source = cache["source"].get(instance.task_type)

        rows.append(
            {
                "id": instance.id,
                "account_id": account.id,
                "account_name": account.nickname
                or account.display_name
                or str(account.id),
                "task_type": instance.task_type,
                "status": instance.status,
                "reset_type": effective_reset_type.value,
                "last_completed_at": instance.last_completed_at,
                "last_completed_at_iso": format_datetime_iso(
                    instance.last_completed_at
                ),
                "updated_at": instance.updated_at,
                "error_message": instance.error_message,
                "next_run_at": next_run_at,
                "next_run_at_iso": format_datetime_iso(next_run_at),
                "interval_seconds": interval_seconds,
                "plan_name": plan_source["name"] if plan_source else None,
                "plan_priority": plan_source["priority"] if plan_source else None,
            }
        )

    return rows, has_more
