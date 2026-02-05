from typing import Any
from typing import Any

from urllib.parse import urlencode

from sqlmodel import Session

from ptcgp_auto_v2.core.task_plan_utils import (
    build_account_plan_cache,
    compute_next_run_for_instance,
)
from ptcgp_auto_v2.db.models.account import Account
from ptcgp_auto_v2.db.repositories import TaskInstanceRepository
from ptcgp_auto_v2.web.queries.task_queries import fetch_task_instances
from ptcgp_auto_v2.web.utils.view_helpers import format_datetime_iso


def build_tasks_page_url(
    page: int,
    lang: str,
    status: list[str],
    task_type: list[str],
    account_id: int | None,
    sort_by: str,
    sort_order: str,
) -> str:
    """构建任务分页 URL。"""
    params = [("page", page), ("lang", lang)]
    for item in status:
        params.append(("status", item))
    for item in task_type:
        params.append(("task_type", item))
    if account_id is not None:
        params.append(("account_id", account_id))
    if sort_by:
        params.append(("sort_by", sort_by))
    if sort_order:
        params.append(("sort_order", sort_order))
    return f"/api/tasks?{urlencode(params)}"


def list_task_status_view(
    session: Session,
    page: int,
    page_size: int,
    status: list[str],
    task_type: list[str],
    account_id: int | None,
    sort_by: str,
    sort_order: str,
) -> tuple[list[dict[str, Any]], bool]:
    """获取任务状态视图数据。"""
    instances, has_more = fetch_task_instances(
        session=session,
        page=page,
        page_size=page_size,
        status=status,
        task_type=task_type,
        account_id=account_id,
        sort_by=sort_by,
        sort_order=sort_order,
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
        computed_next_run_at, effective_reset_type, interval_seconds, plan_source = (
            compute_next_run_for_instance(instance, cache)
        )
        next_run_at = instance.next_run_at or computed_next_run_at

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


def recompute_next_run_at_for_account(
    account: Account, task_types: list[str] | None
) -> None:
    """重算指定账号的任务 next_run_at。"""
    if account.id is None:
        return
    account_cache = build_account_plan_cache(account)
    if task_types is None:
        task_types = list(account_cache["config"].keys())
    if not task_types:
        return
    repo = TaskInstanceRepository()
    instances = repo.list_by_account_and_task_types(account.id, task_types)
    if not instances:
        return
    for instance in instances:
        next_run_at, _, _, _ = compute_next_run_for_instance(instance, account_cache)
        instance.next_run_at = next_run_at
    repo.update_next_run_at(instances)
