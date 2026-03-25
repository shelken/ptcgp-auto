# -*- coding: utf-8 -*-
"""查询层公共分页与排序工具。"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, TypeVar

from sqlalchemy import func
from sqlmodel import Session, select

from ptcgp_auto_v2.web.utils.filter_utils import (
    normalize_page,
    normalize_page_size,
    normalize_sort_order,
)


SortColumnT = TypeVar("SortColumnT")


def normalize_sort_params(
    *,
    sort_by: str,
    sort_order: str,
    allowed_fields: Mapping[str, Any],
    default_field: str,
) -> tuple[str, str]:
    """归一化排序字段与排序方向。"""
    normalized_sort_by = sort_by if sort_by in allowed_fields else default_field
    return normalized_sort_by, normalize_sort_order(sort_order)


def normalize_pagination(
    *,
    page: int,
    page_size: int,
    min_size: int = 1,
    max_size: int = 100,
) -> tuple[int, int]:
    """归一化分页参数。"""
    return normalize_page(page), normalize_page_size(
        page_size, min_size=min_size, max_size=max_size
    )


def resolve_sort_column(
    *,
    sort_by: str,
    fields: Mapping[str, SortColumnT],
    default_field: str,
) -> SortColumnT:
    """根据字段名解析排序列。"""
    if sort_by in fields:
        return fields[sort_by]
    return fields[default_field]


def apply_sort(statement: Any, *, sort_column: Any, sort_order: str) -> Any:
    """按方向应用排序列。"""
    if sort_order == "asc":
        return statement.order_by(sort_column.asc())
    return statement.order_by(sort_column.desc())


def count_rows(session: Session, statement: Any) -> int:
    """统计查询语句总行数。"""
    count_statement = select(func.count()).select_from(statement.order_by(None).subquery())
    return int(session.exec(count_statement).one() or 0)


def fetch_page_rows(
    *,
    session: Session,
    statement: Any,
    page: int,
    page_size: int,
) -> list[Any]:
    """执行严格分页查询并返回当前页行。"""
    offset = page * page_size
    return list(session.exec(statement.offset(offset).limit(page_size)).all())


def fetch_page_rows_with_total(
    *,
    session: Session,
    statement: Any,
    page: int,
    page_size: int,
) -> tuple[list[Any], int]:
    """执行严格分页查询并返回总数。"""
    total = count_rows(session, statement)
    rows = fetch_page_rows(
        session=session,
        statement=statement,
        page=page,
        page_size=page_size,
    )
    return rows, total


def fetch_window_rows(
    *,
    session: Session,
    statement: Any,
    page: int,
    page_size: int,
) -> tuple[list[Any], bool]:
    """执行 +1 分页窗口查询并返回是否存在下一页。"""
    offset = page * page_size
    rows = list(session.exec(statement.offset(offset).limit(page_size + 1)).all())
    has_next = len(rows) > page_size
    if has_next:
        rows = rows[:page_size]
    return rows, has_next
