import json
from typing import Any

from sqlmodel import Session

from ptcgp_auto_v2.core.scheduling_service import recompute_and_sync_account_scheduling
from ptcgp_auto_v2.core.task_base import TaskRegistry, ResetType
from ptcgp_auto_v2.db.engine import session_scope
from ptcgp_auto_v2.db.models.task_plan import TaskPlan
from ptcgp_auto_v2.db.repositories import AccountRepository, TaskPlanRepository
from ptcgp_auto_v2.web.utils.form_utils import safe_get_string
from ptcgp_auto_v2.web.utils.filter_utils import (
    normalize_query_text,
    normalize_page,
    normalize_page_size,
    normalize_sort_order,
)
from ptcgp_auto_v2.web.utils.serialization import serialize_task_plan


def _serialize_plan(plan: TaskPlan) -> dict[str, Any]:
    """把计划转成模板可直接使用的纯数据。"""
    return serialize_task_plan(plan)


def build_plans_list_context(
    *,
    session: Session,
    q: str = "",
    sort_by: str = "id",
    sort_order: str = "asc",
    page: int = 0,
    page_size: int = 10,
) -> dict:
    """构建计划列表视图上下文（统一列表协议：q/sort/page）。"""
    normalized_q = normalize_query_text(q)
    allowed_sort_fields = {"id", "name"}
    normalized_sort_by = sort_by if sort_by in allowed_sort_fields else "id"
    normalized_sort_order = normalize_sort_order(sort_order)
    normalized_page = normalize_page(page)
    normalized_page_size = normalize_page_size(page_size)
    repo = TaskPlanRepository(session)
    plans_page, total = repo.list_page(
        q=normalized_q,
        sort_by=normalized_sort_by,
        sort_order=normalized_sort_order,
        page=normalized_page,
        page_size=normalized_page_size,
    )
    plans_page = [_serialize_plan(item) for item in plans_page]
    has_prev = normalized_page > 0
    has_next = (normalized_page + 1) * normalized_page_size < total

    return {
        "items": plans_page,
        "q": q,
        "sort_by": normalized_sort_by,
        "sort_order": normalized_sort_order,
        "page": normalized_page,
        "page_size": normalized_page_size,
        "has_prev": has_prev,
        "has_next": has_next,
        "total": total,
    }


def build_plan_edit_context(plan_id: int | None) -> dict:
    """构建计划编辑弹窗数据。"""
    with session_scope() as session:
        repo = TaskPlanRepository(session)
        plan = repo.get_by_id(plan_id) if plan_id else None

        available_tasks = TaskRegistry.all_types()
        reset_types = [item.value for item in ResetType]

        if plan and plan.task_types_list:
            ordered_enabled_tasks = [
                item for item in plan.task_types_list if item in available_tasks
            ]
            ordered_disabled_tasks = [
                item for item in available_tasks if item not in plan.task_types_list
            ]
            ordered_tasks = ordered_enabled_tasks + ordered_disabled_tasks
        else:
            ordered_tasks = available_tasks

        return {
            "plan": _serialize_plan(plan) if plan else None,
            "available_tasks": ordered_tasks,
            "reset_types": reset_types,
        }


def upsert_plan_from_form(form) -> str | None:
    """根据表单创建或更新任务计划。返回错误消息或 None（成功）。"""
    plan_id = safe_get_string(form, "plan_id")
    name = safe_get_string(form, "name") or ""
    description = safe_get_string(form, "description")
    task_order = _parse_task_order(form)
    enabled_task_types, configuration = _collect_enabled_tasks_and_config(form)
    task_types = _build_task_types_from_form(form, task_order, enabled_task_types)

    with session_scope() as session:
        repo = TaskPlanRepository(session)
        plan = _upsert_plan_entity(
            repo=repo,
            plan_id=plan_id,
            name=name,
            description=description,
            task_types=task_types,
            configuration=configuration,
        )
        if isinstance(plan, str):
            return plan

        if plan and plan.id is not None:
            account_repo = AccountRepository(session)
            accounts = account_repo.list_accounts_by_plan_id(plan.id)
            for account in accounts:
                if account.id is None:
                    continue
                recompute_and_sync_account_scheduling(
                    session=session,
                    account_id=account.id,
                )

    return None


def _parse_task_order(form) -> list[Any]:
    """解析任务顺序 JSON。"""
    task_order_str = safe_get_string(form, "task_order")
    if not task_order_str:
        return []
    try:
        task_order = json.loads(task_order_str)
    except (json.JSONDecodeError, TypeError):
        return []
    if not isinstance(task_order, list):
        return []
    return task_order


def _collect_enabled_tasks_and_config(
    form,
) -> tuple[set[str], dict[str, dict[str, Any]]]:
    """收集启用任务与任务配置。"""
    enabled_task_types: set[str] = set()
    configuration: dict[str, dict[str, Any]] = {}
    for key in form:
        if not key.startswith("task_enabled_"):
            continue
        task_type = key.replace("task_enabled_", "")
        enabled_task_types.add(task_type)
        task_config = _build_single_task_config(form, task_type)
        if task_config:
            configuration[task_type] = task_config
    return enabled_task_types, configuration


def _build_single_task_config(form, task_type: str) -> dict[str, Any]:
    """构建单个任务配置。"""
    reset_type = safe_get_string(form, f"task_reset_{task_type}")
    interval = safe_get_string(form, f"task_interval_{task_type}")
    task_config: dict[str, Any] = {}
    if not reset_type or not isinstance(reset_type, str) or reset_type == "default":
        return task_config
    task_config["reset_type"] = reset_type
    if reset_type != "interval" or not interval or not isinstance(interval, str):
        return task_config
    try:
        task_config["interval_seconds"] = int(interval)
    except ValueError:
        return task_config
    return task_config


def _build_task_types_from_form(
    form,
    task_order: list[Any],
    enabled_task_types: set[str],
) -> list[Any]:
    """按顺序生成最终 task_types 列表。"""
    if task_order:
        return [item for item in task_order if item in enabled_task_types]
    task_types: list[str] = []
    for key in form:
        if key.startswith("task_enabled_"):
            task_types.append(key.replace("task_enabled_", ""))
    return task_types


def _upsert_plan_entity(
    *,
    repo: TaskPlanRepository,
    plan_id: str | None,
    name: str,
    description: str | None,
    task_types: list[Any],
    configuration: dict[str, dict[str, Any]],
) -> TaskPlan | str:
    """更新或创建计划，冲突时返回冲突名称。"""
    plan = _resolve_existing_plan(repo, plan_id)
    if plan is not None:
        if plan.name != name and _plan_name_exists_for_other(repo, name, plan.id):
            return name
        plan.name = name
        plan.description = description
        plan.task_types = json.dumps(task_types)
        plan.configuration = json.dumps(configuration)
        if not repo.update(plan):
            pid_str = plan_id if isinstance(plan_id, str) else str(plan_id)
            print(f"ERROR: Failed to update plan {pid_str}")
        return plan

    if _plan_name_exists_for_other(repo, name, None):
        return name
    new_plan = TaskPlan(
        name=name,
        description=description,
        task_types=json.dumps(task_types),
        configuration=json.dumps(configuration),
    )
    return repo.create(new_plan)


def _resolve_existing_plan(
    repo: TaskPlanRepository,
    plan_id: str | None,
) -> TaskPlan | None:
    """根据 plan_id 解析已存在计划。"""
    if not plan_id or not isinstance(plan_id, str) or not plan_id.isdigit():
        return None
    return repo.get_by_id(int(plan_id))


def _plan_name_exists_for_other(
    repo: TaskPlanRepository,
    name: str,
    current_plan_id: int | None,
) -> bool:
    """检查名称是否被其他计划占用。"""
    existing = repo.get_by_name(name)
    if existing is None:
        return False
    if current_plan_id is None:
        return True
    return existing.id != current_plan_id


def delete_plan_by_id(plan_id: int) -> None:
    """删除任务计划。"""
    with session_scope() as session:
        account_repo = AccountRepository(session)
        affected_account_ids = [
            account.id
            for account in account_repo.list_accounts_by_plan_id(plan_id)
            if account.id is not None
        ]

        repo = TaskPlanRepository(session)
        repo.delete(plan_id)

        for account_id in affected_account_ids:
            recompute_and_sync_account_scheduling(
                session=session,
                account_id=account_id,
            )
