# -*- coding: utf-8 -*-
"""任务排序策略。

统一维护调度与 Web 列表的任务排序规则，避免多处重复实现导致行为漂移。
"""

from typing import Any, cast

from sqlmodel import case, col

from ptcgp_auto_v2.db.models import TaskInstance

TASK_SORT_BY_DISPATCH_PRIORITY = "dispatch_priority"
TASK_SORT_BY_LAST_COMPLETED = "last_completed_at"
TASK_SORT_BY_NEXT_RUN = "next_run_at"


def normalize_task_sort(sort_by: str | None, sort_order: str | None) -> tuple[str, str]:
    """标准化任务排序参数。"""
    allowed_sort_by = {
        TASK_SORT_BY_DISPATCH_PRIORITY,
        TASK_SORT_BY_LAST_COMPLETED,
        TASK_SORT_BY_NEXT_RUN,
    }
    normalized_sort_by = (
        sort_by if sort_by in allowed_sort_by else TASK_SORT_BY_DISPATCH_PRIORITY
    )

    if normalized_sort_by == TASK_SORT_BY_DISPATCH_PRIORITY:
        # 调度优先级固定升序，避免前端误传参数影响调度语义
        normalized_sort_order = "asc"
    else:
        normalized_sort_order = "asc" if sort_order == "asc" else "desc"

    return normalized_sort_by, normalized_sort_order


def build_task_instance_order_by(sort_by: str, sort_order: str) -> list:
    """构建 TaskInstance 的统一排序表达式。"""
    normalized_sort_by, normalized_sort_order = normalize_task_sort(sort_by, sort_order)

    next_run_col = col(cast(Any, TaskInstance.next_run_at))
    last_completed_col = col(cast(Any, TaskInstance.last_completed_at))

    if normalized_sort_by == TASK_SORT_BY_DISPATCH_PRIORITY:
        reset_priority = case((TaskInstance.reset_type == "once", 0), else_=1)
        return [
            reset_priority.asc(),
            next_run_col.asc().nulls_first(),
            last_completed_col.asc().nulls_first(),
        ]

    if normalized_sort_by == TASK_SORT_BY_NEXT_RUN:
        if normalized_sort_order == "asc":
            return [next_run_col.asc().nulls_first()]
        return [next_run_col.desc().nulls_first()]

    if normalized_sort_order == "asc":
        return [last_completed_col.asc().nulls_first()]
    return [last_completed_col.desc().nulls_first()]
