# -*- coding: utf-8 -*-
"""资源页查询层。"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from sqlalchemy import String, case, cast, func, or_
from sqlalchemy.orm import aliased
from sqlmodel import Session, select

from ptcgp_auto_v2.db.models import Account, AccountPackPoint, AccountStat
from ptcgp_auto_v2.web.queries._query_helpers import count_rows, fetch_page_rows
from ptcgp_auto_v2.web.utils.filter_utils import (
    normalize_page,
    normalize_page_size,
    normalize_query_text,
    normalize_sort_order,
)


def _apply_account_search(statement, normalized_q: str):
    """按账号页既有语义追加搜索条件。"""
    if not normalized_q:
        return statement

    like_text = f"%{normalized_q}%"
    return statement.where(
        or_(
            cast(Account.id, String).ilike(like_text),
            Account.nickname.ilike(like_text),
            Account.friend_id.ilike(like_text),
            Account.game_id.ilike(like_text),
        )
    )


def _apply_nulls_last_order(statement, sort_column, sort_order: str, tie_breaker):
    """为排序字段追加 NULL 最后与稳定次序。"""
    nulls_last_flag = case((sort_column.is_(None), 1), else_=0)
    if sort_order == "desc":
        return statement.order_by(
            nulls_last_flag.asc(), sort_column.desc(), tie_breaker.asc()
        )
    return statement.order_by(
        nulls_last_flag.asc(), sort_column.asc(), tie_breaker.asc()
    )


def _build_account_resource_row(row: Sequence[Any]) -> dict[str, Any]:
    """将账号资源查询结果转换为简单字典。"""
    (
        account_id,
        nickname,
        friend_id,
        game_id,
        exchange_points,
        pack_hourglass_count,
        updated_at,
    ) = row
    return {
        "account_id": account_id,
        "nickname": nickname,
        "friend_id": friend_id,
        "game_id": game_id,
        "exchange_points": exchange_points,
        "pack_hourglass_count": pack_hourglass_count,
        "updated_at": updated_at,
    }


def list_account_resources(
    *,
    session: Session,
    q: str = "",
    sort_by: str = "id",
    sort_order: str = "asc",
    page: int = 0,
    page_size: int = 20,
) -> tuple[list[dict[str, Any]], int]:
    """分页查询账号资源列表。"""
    normalized_q = normalize_query_text(q)
    normalized_sort_order = normalize_sort_order(sort_order)
    normalized_page = normalize_page(page)
    normalized_page_size = normalize_page_size(page_size)

    resource_updated_at = func.coalesce(AccountStat.updated_at, Account.updated_at)
    statement = (
        select(
            Account.id,
            Account.nickname,
            Account.friend_id,
            Account.game_id,
            AccountStat.exchange_points,
            AccountStat.pack_hourglass_count,
            resource_updated_at.label("updated_at"),
        )
        .select_from(Account)
        .outerjoin(AccountStat, AccountStat.account_id == Account.id)
    )
    statement = _apply_account_search(statement, normalized_q)

    allowed_sort_columns = {
        "id": Account.id,
        "nickname": func.lower(Account.nickname),
        "friend_id": func.lower(Account.friend_id),
        "exchange_points": AccountStat.exchange_points,
        "pack_hourglass_count": AccountStat.pack_hourglass_count,
        "updated_at": resource_updated_at,
    }
    sort_column = allowed_sort_columns.get(sort_by, Account.id)
    statement = _apply_nulls_last_order(
        statement=statement,
        sort_column=sort_column,
        sort_order=normalized_sort_order,
        tie_breaker=Account.id,
    )

    total = count_rows(session, statement)
    page_rows = fetch_page_rows(
        session=session,
        statement=statement,
        page=normalized_page,
        page_size=normalized_page_size,
    )
    rows = [_build_account_resource_row(row) for row in page_rows]
    return rows, total


def _extract_series_sort_code(sort_by: str) -> str | None:
    """解析系列排序字段。"""
    if not sort_by.startswith("series:"):
        return None
    series_code = sort_by.split(":", 1)[1].strip()
    return series_code or None


def _build_pack_point_rows(
    account_rows: Sequence[Sequence[Any]],
    point_rows: Sequence[AccountPackPoint],
) -> list[dict[str, Any]]:
    """将账号列表与包点数记录组装为页面行数据。"""
    series_points_map: dict[int, dict[str, int]] = {}
    for point_row in point_rows:
        account_series_points = series_points_map.setdefault(point_row.account_id, {})
        account_series_points[point_row.series] = point_row.points

    rows: list[dict[str, Any]] = []
    for account_id, nickname, friend_id, game_id in account_rows:
        rows.append(
            {
                "account_id": account_id,
                "nickname": nickname,
                "friend_id": friend_id,
                "game_id": game_id,
                "series_points": series_points_map.get(account_id, {}),
            }
        )
    return rows


def list_pack_point_resources(
    *,
    session: Session,
    q: str = "",
    sort_by: str = "id",
    sort_order: str = "asc",
    page: int = 0,
    page_size: int = 20,
) -> dict[str, Any]:
    """分页查询账号包点数资源列表。"""
    normalized_q = normalize_query_text(q)
    normalized_sort_order = normalize_sort_order(sort_order)
    normalized_page = normalize_page(page)
    normalized_page_size = normalize_page_size(page_size)

    series_list_statement = (
        select(AccountPackPoint.series)
        .distinct()
        .order_by(AccountPackPoint.series.asc())
    )
    series_list = list(session.exec(series_list_statement).all())

    base_statement = select(
        Account.id,
        Account.nickname,
        Account.friend_id,
        Account.game_id,
    ).select_from(Account)
    base_statement = _apply_account_search(base_statement, normalized_q)

    series_sort_code = _extract_series_sort_code(sort_by)
    if series_sort_code:
        series_sort_alias = aliased(AccountPackPoint)
        base_statement = base_statement.outerjoin(
            series_sort_alias,
            (series_sort_alias.account_id == Account.id)
            & (series_sort_alias.series == series_sort_code),
        )
        base_statement = _apply_nulls_last_order(
            statement=base_statement,
            sort_column=series_sort_alias.points,
            sort_order=normalized_sort_order,
            tie_breaker=Account.id,
        )
    else:
        allowed_sort_columns = {
            "id": Account.id,
            "nickname": func.lower(Account.nickname),
            "friend_id": func.lower(Account.friend_id),
        }
        sort_column = allowed_sort_columns.get(sort_by, Account.id)
        base_statement = _apply_nulls_last_order(
            statement=base_statement,
            sort_column=sort_column,
            sort_order=normalized_sort_order,
            tie_breaker=Account.id,
        )

    total = count_rows(session, base_statement)
    paged_account_rows = fetch_page_rows(
        session=session,
        statement=base_statement,
        page=normalized_page,
        page_size=normalized_page_size,
    )
    account_ids = [row[0] for row in paged_account_rows]

    point_rows: list[AccountPackPoint] = []
    if account_ids:
        point_statement = select(AccountPackPoint).where(
            AccountPackPoint.account_id.in_(account_ids)
        )
        point_rows = list(session.exec(point_statement).all())

    return {
        "rows": _build_pack_point_rows(paged_account_rows, point_rows),
        "total": total,
        "series_list": series_list,
    }
