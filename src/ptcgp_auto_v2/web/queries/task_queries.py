from typing import Any, cast

from typing import Any, cast

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
