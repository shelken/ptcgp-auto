import json

from sqlmodel import Session

from ptcgp_auto_v2.core.task_base import TaskRegistry, ResetType
from ptcgp_auto_v2.db.models.task_plan import TaskPlan
from ptcgp_auto_v2.db.repositories import AccountRepository, TaskPlanRepository
from ptcgp_auto_v2.web.services.task_service import recompute_next_run_at_for_account
from ptcgp_auto_v2.web.utils.form_utils import safe_get_string
from ptcgp_auto_v2.web.utils.filter_utils import (
    normalize_query_text,
    normalize_page,
    normalize_page_size,
    normalize_sort_order,
)


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
    repo = TaskPlanRepository()
    plans = repo.get_all()

    normalized_q = normalize_query_text(q)
    allowed_sort_fields = {"id", "name"}
    normalized_sort_by = sort_by if sort_by in allowed_sort_fields else "id"
    normalized_sort_order = normalize_sort_order(sort_order)
    normalized_page = normalize_page(page)
    normalized_page_size = normalize_page_size(page_size)

    if normalized_q:
        plans = [
            item
            for item in plans
            if normalized_q in str(item.id or "")
            or normalized_q in (item.name or "").lower()
            or normalized_q in (item.description or "").lower()
        ]

    def _sort_value(item: TaskPlan):
        if normalized_sort_by == "name":
            return (item.name or "").lower()
        return item.id or 0

    plans = sorted(
        plans,
        key=_sort_value,
        reverse=(normalized_sort_order == "desc"),
    )

    total = len(plans)
    start = normalized_page * normalized_page_size
    end = start + normalized_page_size
    plans_page = plans[start:end]
    has_prev = normalized_page > 0
    has_next = end < total

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
    repo = TaskPlanRepository()
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
        "plan": plan,
        "available_tasks": ordered_tasks,
        "reset_types": reset_types,
    }


def upsert_plan_from_form(form) -> str | None:
    """根据表单创建或更新任务计划。返回错误消息或 None（成功）。"""
    plan_id = safe_get_string(form, "plan_id")
    name = safe_get_string(form, "name") or ""
    description = safe_get_string(form, "description")

    task_order_str = safe_get_string(form, "task_order")
    task_order = []
    if task_order_str:
        try:
            task_order = json.loads(task_order_str)
        except (json.JSONDecodeError, TypeError):
            task_order = []

    configuration = {}
    enabled_task_types = set()

    for key in form:
        if key.startswith("task_enabled_"):
            task_type = key.replace("task_enabled_", "")
            enabled_task_types.add(task_type)

            reset_type = safe_get_string(form, f"task_reset_{task_type}")
            interval = safe_get_string(form, f"task_interval_{task_type}")

            task_config = {}
            if reset_type and isinstance(reset_type, str) and reset_type != "default":
                task_config["reset_type"] = reset_type
                if reset_type == "interval" and interval and isinstance(interval, str):
                    try:
                        task_config["interval_seconds"] = int(interval)
                    except ValueError:
                        pass

            if task_config:
                configuration[task_type] = task_config

    if task_order:
        task_types = [item for item in task_order if item in enabled_task_types]
    else:
        task_types = []
        for key in form:
            if key.startswith("task_enabled_"):
                task_type = key.replace("task_enabled_", "")
                task_types.append(task_type)

    repo = TaskPlanRepository()
    plan = None
    if plan_id:
        val = plan_id
        if isinstance(val, str) and val.isdigit():
            plan = repo.get_by_id(int(val))
        if plan:
            # 更新时检查新名称是否与其他计划重复
            if plan.name != name:
                existing = repo.get_by_name(name)
                if existing and existing.id != plan.id:
                    return name
            plan.name = name
            plan.description = description
            plan.task_types = json.dumps(task_types)
            plan.configuration = json.dumps(configuration)
            if not repo.update(plan):
                pid_str = val if isinstance(val, str) else str(plan_id)
                print(f"ERROR: Failed to update plan {pid_str}")

    if not plan:
        # 创建时检查名称是否已存在
        existing = repo.get_by_name(name)
        if existing:
            return name
        plan = TaskPlan(
            name=name,
            description=description,
            task_types=json.dumps(task_types),
            configuration=json.dumps(configuration),
        )
        plan = repo.create(plan)

    if plan and plan.id is not None:
        account_repo = AccountRepository()
        accounts = account_repo.list_accounts_by_plan_id(plan.id)
        for account in accounts:
            recompute_next_run_at_for_account(account, plan.task_types_list)

    return None


def delete_plan_by_id(plan_id: int) -> None:
    """删除任务计划。"""
    repo = TaskPlanRepository()
    repo.delete(plan_id)
