import json

from ptcgp_auto_v2.core.task_base import TaskRegistry, ResetType
from ptcgp_auto_v2.db.models.task_plan import TaskPlan
from ptcgp_auto_v2.db.repositories import AccountRepository, TaskPlanRepository
from ptcgp_auto_v2.web.services.task_service import recompute_next_run_at_for_account
from ptcgp_auto_v2.web.utils.form_utils import safe_get_string
from ptcgp_auto_v2.web.utils.i18n import get_translations, normalize_lang


def get_plans_context(lang: str) -> dict:
    """获取计划列表视图数据。"""
    current_lang = normalize_lang(lang)
    t = get_translations(current_lang)
    repo = TaskPlanRepository()
    plans = repo.get_all()
    return {"plans": plans, "t": t, "current_lang": current_lang}


def build_plan_edit_context(plan_id: int | None, lang: str) -> dict:
    """构建计划编辑弹窗数据。"""
    current_lang = normalize_lang(lang)
    t = get_translations(current_lang)
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
        "t": t,
        "current_lang": current_lang,
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
