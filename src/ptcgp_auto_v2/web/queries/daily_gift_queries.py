# -*- coding: utf-8 -*-
"""
每日送卡管理查询模块。

将统计、记录列表、配对进度拆分为独立查询，避免不同区块共用同一批截断结果。
"""

from typing import Any

from sqlalchemy import String, and_, cast, case, func, or_
from sqlalchemy.orm import aliased
from sqlmodel import Session, col, select

from ptcgp_auto_v2.db.models import Account, AccountGiftPair, AccountGiftRecord


def _normalize_record_sort(sort_by: str, sort_order: str) -> tuple[str, str]:
    """规范化送卡记录排序字段。"""
    allowed_sort = {"updated_at", "account_id", "status"}
    normalized_sort_by = sort_by if sort_by in allowed_sort else "updated_at"
    normalized_sort_order = "asc" if sort_order == "asc" else "desc"
    return normalized_sort_by, normalized_sort_order


def _build_record_query(
    *,
    biz_date_local: str,
    account_id: int | None,
    q: str,
) -> tuple[Any, Any, Any]:
    """构建送卡记录查询基础语句，并返回源账号/目标账号别名。"""
    source_account = aliased(Account)
    target_account = aliased(Account)

    statement = (
        select(AccountGiftRecord)
        .join(source_account, source_account.id == AccountGiftRecord.account_id)
        .outerjoin(target_account, target_account.id == AccountGiftRecord.target_account_id)
        .where(AccountGiftRecord.biz_date_local == biz_date_local)
    )

    if account_id is not None:
        statement = statement.where(
            or_(
                AccountGiftRecord.account_id == account_id,
                AccountGiftRecord.target_account_id == account_id,
            )
        )

    normalized_q = q.strip().lower()
    if normalized_q:
        like_pattern = f"%{normalized_q}%"
        statement = statement.where(
            or_(
                func.lower(cast(AccountGiftRecord.account_id, String)).like(like_pattern),
                func.lower(cast(AccountGiftRecord.target_account_id, String)).like(
                    like_pattern
                ),
                func.lower(func.coalesce(AccountGiftRecord.target_friend_id, "")).like(
                    like_pattern
                ),
                func.lower(func.coalesce(source_account.nickname, "")).like(like_pattern),
                func.lower(func.coalesce(source_account.friend_id, "")).like(like_pattern),
                func.lower(func.coalesce(source_account.game_id, "")).like(like_pattern),
                func.lower(func.coalesce(target_account.nickname, "")).like(like_pattern),
                func.lower(func.coalesce(target_account.friend_id, "")).like(like_pattern),
                func.lower(func.coalesce(target_account.game_id, "")).like(like_pattern),
            )
        )

    return statement, source_account, target_account


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
    q: str,
    sort_by: str,
    sort_order: str,
    page: int,
    page_size: int,
) -> tuple[list[AccountGiftRecord], bool, int]:
    """查询每日送卡记录分页数据。"""
    statement, _, _ = _build_record_query(
        biz_date_local=biz_date_local,
        account_id=account_id,
        q=q,
    )
    total_statement, _, _ = _build_record_query(
        biz_date_local=biz_date_local,
        account_id=account_id,
        q=q,
    )

    total = int(
        session.exec(
            select(func.count()).select_from(total_statement.subquery())
        ).one()
        or 0
    )

    normalized_sort_by, normalized_sort_order = _normalize_record_sort(
        sort_by,
        sort_order,
    )
    reverse = normalized_sort_order == "desc"

    if normalized_sort_by == "account_id":
        primary_order = col(AccountGiftRecord.account_id).desc() if reverse else col(
            AccountGiftRecord.account_id
        ).asc()
    elif normalized_sort_by == "status":
        primary_order = col(AccountGiftRecord.status).desc() if reverse else col(
            AccountGiftRecord.status
        ).asc()
    else:
        primary_order = col(AccountGiftRecord.updated_at).desc() if reverse else col(
            AccountGiftRecord.updated_at
        ).asc()

    offset = page * page_size
    rows = list(
        session.exec(
            statement.order_by(
                primary_order,
                col(AccountGiftRecord.id).desc() if reverse else col(AccountGiftRecord.id).asc(),
            )
            .offset(offset)
            .limit(page_size + 1)
        ).all()
    )
    has_next = len(rows) > page_size
    if has_next:
        rows = rows[:page_size]
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
    """查询当前有效送卡配对记录。"""
    statement = select(AccountGiftPair).where(AccountGiftPair.is_active.is_(True))
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
