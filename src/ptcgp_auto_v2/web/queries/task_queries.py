from typing import Any, cast

from datetime import datetime

from sqlalchemy import update
from sqlmodel import Session, select, col, func
from sqlalchemy.orm import selectinload

from ptcgp_auto_v2.core.scheduling_service import build_task_instance_order_by
from ptcgp_auto_v2.db.models.task_instance import TaskInstance
from ptcgp_auto_v2.db.models.account import Account
from ptcgp_auto_v2.db.models.account_task_plan import AccountTaskPlan
from ptcgp_auto_v2.web.queries._query_helpers import (
    fetch_window_rows,
    normalize_pagination,
)


def _build_task_instance_filters(
    statement: Any,
    *,
    status: list[str],
    task_type: list[str],
    account_id: int | None,
) -> Any:
    """为任务查询语句附加统一过滤条件。"""
    if status:
        statement = statement.where(col(TaskInstance.status).in_(status))
    if task_type:
        statement = statement.where(col(TaskInstance.task_type).in_(task_type))
    if account_id is not None:
        statement = statement.where(TaskInstance.account_id == account_id)
    return statement


def fetch_task_instances(
    session: Session,
    page: int,
    page_size: int,
    status: list[str],
    task_type: list[str],
    account_id: int | None,
    sort_by: str,
    sort_order: str,
) -> tuple[list[TaskInstance], bool, int]:
    """查询任务实例列表，返回分页数据、是否有下一页和总数。"""
    normalized_page, normalized_page_size = normalize_pagination(
        page=page,
        page_size=page_size,
        max_size=100,
    )
    statement = select(TaskInstance).options(
        selectinload(cast(Any, TaskInstance.account))  # type: ignore[arg-type]
        .selectinload(cast(Any, Account.task_plan_associations))  # type: ignore[arg-type]
        .selectinload(cast(Any, AccountTaskPlan.task_plan))  # type: ignore[arg-type]
    )

    statement = _build_task_instance_filters(
        statement,
        status=status,
        task_type=task_type,
        account_id=account_id,
    )

    total_statement = _build_task_instance_filters(
        select(func.count()).select_from(TaskInstance),
        status=status,
        task_type=task_type,
        account_id=account_id,
    )
    total = int(session.exec(total_statement).one())

    statement = statement.order_by(*build_task_instance_order_by(sort_by, sort_order))
    instances, has_next = fetch_window_rows(
        session=session,
        statement=statement,
        page=normalized_page,
        page_size=normalized_page_size,
    )
    return instances, has_next, total


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

    # 手动重置已完成任务时，清空 next_run_at，确保调度按“立即可执行”优先处理。
    statement = statement.values(
        status="pending",
        next_run_at=None,
        status_changed_at=datetime.now(),
        updated_at=datetime.now(),
    )
    result = session.exec(statement)

    session.commit()
    return result.rowcount or 0
