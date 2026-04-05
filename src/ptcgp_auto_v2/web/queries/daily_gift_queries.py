# -*- coding: utf-8 -*-
"""
每日送卡管理查询模块。

将统计、记录列表、配对进度拆分为独立查询，避免不同区块共用同一批截断结果。
"""

from typing import Any

from sqlalchemy import and_, case, func, or_
from sqlmodel import Session, col, select

from ptcgp_auto_v2.db.models import Account, AccountGiftPair, AccountGiftRecord
from ptcgp_auto_v2.web.queries._query_helpers import (
    count_rows,
    fetch_window_rows,
    normalize_pagination,
    normalize_sort_params,
    resolve_sort_column,
)


RECORD_SORT_FIELDS = {
    "updated_at": col(AccountGiftRecord.updated_at),
    "account_id": col(AccountGiftRecord.account_id),
    "status": col(AccountGiftRecord.status),
}


def _normalize_record_sort(sort_by: str, sort_order: str) -> tuple[str, str]:
    """规范化送卡记录排序字段。"""
    return normalize_sort_params(
        sort_by=sort_by,
        sort_order=sort_order,
        allowed_fields=RECORD_SORT_FIELDS,
        default_field="updated_at",
    )


def _build_record_query(
    *,
    biz_date_local: str,
    account_id: int | None,
) -> Any:
    """构建送卡记录查询基础语句。"""
    statement = select(AccountGiftRecord).where(
        AccountGiftRecord.biz_date_local == biz_date_local
    )

    if account_id is not None:
        statement = statement.where(
            or_(
                AccountGiftRecord.account_id == account_id,
                AccountGiftRecord.target_account_id == account_id,
            )
        )
    return statement


def fetch_daily_gift_stats(
    session: Session,
    *,
    biz_date_local: str,
    account_id: int | None,
) -> dict[str, int]:
    """查询每日送卡统计。"""
    statement = select(
        func.count(AccountGiftRecord.id),
        func.sum(case((AccountGiftRecord.status == "success", 1), else_=0)),
        func.sum(case((AccountGiftRecord.status == "failed", 1), else_=0)),
        func.sum(
            case(
                (
                    and_(
                        AccountGiftRecord.status != "success",
                        AccountGiftRecord.status != "failed",
                    ),
                    1,
                ),
                else_=0,
            )
        ),
    ).where(AccountGiftRecord.biz_date_local == biz_date_local)

    if account_id is not None:
        statement = statement.where(
            or_(
                AccountGiftRecord.account_id == account_id,
                AccountGiftRecord.target_account_id == account_id,
            )
        )

    total, success, failed, waiting = session.exec(statement).one()
    return {
        "total": int(total or 0),
        "success": int(success or 0),
        "failed": int(failed or 0),
        "waiting": int(waiting or 0),
    }


def fetch_daily_gift_records_page(
    session: Session,
    *,
    biz_date_local: str,
    account_id: int | None,
    sort_by: str,
    sort_order: str,
    page: int,
    page_size: int,
) -> tuple[list[AccountGiftRecord], bool, int]:
    """查询每日送卡记录分页数据。"""
    normalized_page, normalized_page_size = normalize_pagination(
        page=page,
        page_size=page_size,
        max_size=100,
    )
    statement = _build_record_query(
        biz_date_local=biz_date_local,
        account_id=account_id,
    )
    total = count_rows(session, statement)

    normalized_sort_by, normalized_sort_order = _normalize_record_sort(
        sort_by,
        sort_order,
    )
    sort_column = resolve_sort_column(
        sort_by=normalized_sort_by,
        fields=RECORD_SORT_FIELDS,
        default_field="updated_at",
    )
    if normalized_sort_order == "asc":
        ordered_statement = statement.order_by(
            sort_column.asc(),
            col(AccountGiftRecord.id).asc(),
        )
    else:
        ordered_statement = statement.order_by(
            sort_column.desc(),
            col(AccountGiftRecord.id).desc(),
        )
    rows, has_next = fetch_window_rows(
        session=session,
        statement=ordered_statement,
        page=normalized_page,
        page_size=normalized_page_size,
    )
    return rows, has_next, total


def list_daily_gift_pair_records(
    session: Session,
    *,
    biz_date_local: str,
    account_id: int | None,
) -> list[AccountGiftRecord]:
    """查询指定业务日内用于配对进度计算的送卡记录。"""
    statement = select(AccountGiftRecord).where(
        AccountGiftRecord.biz_date_local == biz_date_local,
        col(AccountGiftRecord.target_account_id).is_not(None),
    )

    if account_id is not None:
        statement = statement.where(
            or_(
                AccountGiftRecord.account_id == account_id,
                AccountGiftRecord.target_account_id == account_id,
            )
        )

    statement = statement.order_by(
        col(AccountGiftRecord.updated_at).desc(),
        col(AccountGiftRecord.id).desc(),
    )
    return list(session.exec(statement).all())


def list_active_gift_pairs(
    session: Session,
    *,
    account_id: int | None,
) -> list[AccountGiftPair]:
    """查询当前送卡配对记录。兼容旧函数名。"""
    statement = select(AccountGiftPair)
    if account_id is not None:
        statement = statement.where(
            or_(
                AccountGiftPair.account_id == account_id,
                AccountGiftPair.target_account_id == account_id,
            )
        )
    statement = statement.order_by(
        col(AccountGiftPair.account_id),
        col(AccountGiftPair.target_account_id),
        col(AccountGiftPair.id),
    )
    return list(session.exec(statement).all())


def list_accounts_by_ids(session: Session, account_ids: set[int]) -> list[Account]:
    """按账号 ID 批量查询账号信息。"""
    if not account_ids:
        return []
    statement = select(Account).where(col(Account.id).in_(sorted(account_ids)))
    return list(session.exec(statement).all())


def list_all_accounts(session: Session) -> list[Account]:
    """查询全部账号，用于筛选器选项。"""
    statement = select(Account).order_by(col(Account.id))
    return list(session.exec(statement).all())
