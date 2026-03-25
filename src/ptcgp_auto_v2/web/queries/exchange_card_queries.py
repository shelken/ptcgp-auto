# -*- coding: utf-8 -*-
"""交换卡牌管理查询。"""

from typing import Optional

from sqlalchemy import String, cast, or_
from sqlmodel import Session, col, select

from ptcgp_auto_v2.db.models import ExchangeCardRequest
from ptcgp_auto_v2.web.queries._query_helpers import (
    apply_sort,
    fetch_rows_with_optional_pagination,
    normalize_sort_params,
    resolve_sort_column,
)

SORT_FIELDS = {
    "created_at": col(ExchangeCardRequest.created_at),
    "updated_at": col(ExchangeCardRequest.updated_at),
    "target_card_id": col(ExchangeCardRequest.target_card_id),
    "from_account_id": col(ExchangeCardRequest.from_account_id),
}


def _build_exchange_requests_statement(
    *,
    account_id: Optional[int],
    status: Optional[str],
    q: str,
    sort_by: str,
    sort_order: str,
):
    """构建交换请求列表查询语句。"""
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

    normalized_sort_by, normalized_sort_order = normalize_sort_params(
        sort_by=sort_by,
        sort_order=sort_order,
        allowed_fields=SORT_FIELDS,
        default_field="created_at",
    )
    sort_column = resolve_sort_column(
        sort_by=normalized_sort_by,
        fields=SORT_FIELDS,
        default_field="created_at",
    )
    return apply_sort(
        statement,
        sort_column=sort_column,
        sort_order=normalized_sort_order,
    )


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
    statement = _build_exchange_requests_statement(
        account_id=account_id,
        status=status,
        q=q,
        sort_by=sort_by,
        sort_order=sort_order,
    )

    return fetch_rows_with_optional_pagination(
        session=session,
        statement=statement,
        page=page,
        page_size=page_size,
        max_page_size=100,
    )
