# -*- coding: utf-8 -*-
"""交换卡牌管理查询。"""

from typing import Optional

from sqlalchemy import String, cast, func, or_
from sqlmodel import Session, col, select

from ptcgp_auto_v2.db.models import ExchangeCardRequest


def _normalize_sort(sort_by: str, sort_order: str):
    """标准化排序字段与顺序。"""
    sort_mapping = {
        "created_at": col(ExchangeCardRequest.created_at),
        "updated_at": col(ExchangeCardRequest.updated_at),
        "target_card_id": col(ExchangeCardRequest.target_card_id),
        "from_account_id": col(ExchangeCardRequest.from_account_id),
    }
    sort_column = sort_mapping.get(sort_by, col(ExchangeCardRequest.created_at))
    sort_direction = "asc" if sort_order == "asc" else "desc"
    return sort_column, sort_direction


def list_exchange_requests(
    session: Session,
    account_id: Optional[int] = None,
    status: Optional[str] = None,
    q: str = "",
    sort_by: str = "created_at",
    sort_order: str = "desc",
    page: int | None = None,
    page_size: int | None = None,
) -> tuple[list[ExchangeCardRequest], int] | list[ExchangeCardRequest]:
    """查询交换请求列表，兼容旧版全量接口与新版分页接口。"""
    statement = select(ExchangeCardRequest)
    if account_id is not None:
        statement = statement.where(ExchangeCardRequest.from_account_id == account_id)
    if status:
        statement = statement.where(ExchangeCardRequest.status == status)

    q_text = q.strip()
    if q_text:
        statement = statement.where(
            or_(
                col(ExchangeCardRequest.to_friend_id).ilike(f"%{q_text}%"),
                cast(col(ExchangeCardRequest.from_account_id), String).ilike(
                    f"%{q_text}%"
                ),
                cast(col(ExchangeCardRequest.to_account_id), String).ilike(
                    f"%{q_text}%"
                ),
                cast(col(ExchangeCardRequest.target_card_id), String).ilike(
                    f"%{q_text}%"
                ),
            )
        )

    sort_column, sort_direction = _normalize_sort(sort_by, sort_order)
    if sort_direction == "asc":
        statement = statement.order_by(sort_column.asc())
    else:
        statement = statement.order_by(sort_column.desc())

    if page is None or page_size is None:
        return list(session.exec(statement).all())

    normalized_page = max(page, 0)
    normalized_page_size = min(max(page_size, 1), 100)

    count_stmt = select(func.count()).select_from(statement.subquery())
    total = int(session.exec(count_stmt).one())

    rows = list(
        session.exec(
            statement.offset(normalized_page * normalized_page_size).limit(
                normalized_page_size
            )
        ).all()
    )
    return rows, total
