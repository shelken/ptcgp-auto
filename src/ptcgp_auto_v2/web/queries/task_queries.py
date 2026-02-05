from typing import Any, cast

from datetime import datetime

from sqlalchemy import update
from sqlmodel import Session, select, col
from sqlalchemy.orm import selectinload

from ptcgp_auto_v2.db.models.task_instance import TaskInstance
from ptcgp_auto_v2.db.models.account import Account
from ptcgp_auto_v2.db.models.account_task_plan import AccountTaskPlan


def fetch_task_instances(
    session: Session,
    page: int,
    page_size: int,
    status: list[str],
    task_type: list[str],
    account_id: int | None,
    sort_by: str,
    sort_order: str,
) -> tuple[list[TaskInstance], bool]:
    """查询任务实例列表并返回是否还有下一页。"""
    statement = select(TaskInstance).options(
        selectinload(cast(Any, TaskInstance.account))  # type: ignore[arg-type]
        .selectinload(cast(Any, Account.task_plan_associations))  # type: ignore[arg-type]
        .selectinload(cast(Any, AccountTaskPlan.task_plan))  # type: ignore[arg-type]
    )

    if status:
        statement = statement.where(col(TaskInstance.status).in_(status))
    if task_type:
        statement = statement.where(col(TaskInstance.task_type).in_(task_type))
    if account_id is not None:
        statement = statement.where(TaskInstance.account_id == account_id)

    sort_field = "last_completed_at"
    if sort_by in {"last_completed_at", "next_run_at"}:
        sort_field = sort_by

    order = "desc" if sort_order != "asc" else "asc"

    if sort_field == "next_run_at":
        sort_col = col(cast(Any, TaskInstance.next_run_at))
    else:
        sort_col = col(cast(Any, TaskInstance.last_completed_at))

    if order == "asc":
        statement = statement.order_by(sort_col.is_(None), sort_col.asc())
    else:
        statement = statement.order_by(sort_col.is_(None), sort_col.desc())
    offset = page * page_size
    statement = statement.offset(offset).limit(page_size + 1)
    instances = list(session.exec(statement).all())

    has_more = len(instances) > page_size
    if has_more:
        instances = instances[:page_size]
    return instances, has_more


def reset_completed_task_instances(
    session: Session,
    status: list[str],
    task_type: list[str],
    account_id: int | None,
) -> int:
    """按筛选条件重置已完成任务为待执行。"""
    normalized_status = [item for item in status if item]
    normalized_task_type = [item for item in task_type if item]

    if normalized_status and "completed" not in normalized_status:
        return 0

    filtered_task_types = [
        item for item in normalized_task_type if item != "init_account"
    ]
    if normalized_task_type and not filtered_task_types:
        return 0

    statement = update(TaskInstance).where(TaskInstance.status == "completed")
    if filtered_task_types:
        statement = statement.where(
            col(TaskInstance.task_type).in_(filtered_task_types)
        )
    else:
        statement = statement.where(TaskInstance.task_type != "init_account")
    if account_id is not None:
        statement = statement.where(TaskInstance.account_id == account_id)

    statement = statement.values(status="pending", updated_at=datetime.now())
    result = session.exec(statement)
    session.commit()
    return result.rowcount or 0
