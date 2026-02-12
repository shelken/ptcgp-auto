# -*- coding: utf-8 -*-
"""交换卡牌管理查询。"""

from typing import Optional

from sqlmodel import Session, col, select

from ptcgp_auto_v2.db.models import ExchangeCardRequest


def list_exchange_requests(
    session: Session,
    account_id: Optional[int] = None,
    status: Optional[str] = None,
) -> list[ExchangeCardRequest]:
    """查询交换请求列表。"""
    statement = select(ExchangeCardRequest)
    if account_id is not None:
        statement = statement.where(ExchangeCardRequest.from_account_id == account_id)
    if status:
        statement = statement.where(ExchangeCardRequest.status == status)
    statement = statement.order_by(col(ExchangeCardRequest.created_at).desc())
    return list(session.exec(statement).all())
