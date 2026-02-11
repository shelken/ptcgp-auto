# -*- coding: utf-8 -*-
"""
每日送卡管理查询模块。

封装送卡记录、有效配对和账号基础信息查询，供 Web 服务层组装视图模型。
"""

from sqlmodel import Session, select, col

from ptcgp_auto_v2.db.models import Account, AccountGiftPair, AccountGiftRecord


def list_daily_gift_records(
    session: Session,
    biz_date_local: str,
    limit: int = 200,
) -> list[AccountGiftRecord]:
    """按本地业务日期查询送卡记录，按更新时间倒序。"""
    statement = (
        select(AccountGiftRecord)
        .where(AccountGiftRecord.biz_date_local == biz_date_local)
        .order_by(AccountGiftRecord.updated_at.desc(), AccountGiftRecord.id.desc())
        .limit(limit)
    )
    return list(session.exec(statement).all())


def list_active_gift_pairs(session: Session) -> list[AccountGiftPair]:
    """查询当前有效送卡配对记录。"""
    statement = (
        select(AccountGiftPair)
        .where(AccountGiftPair.is_active.is_(True))
        .order_by(AccountGiftPair.updated_at.desc(), AccountGiftPair.id.desc())
    )
    return list(session.exec(statement).all())


def list_accounts_by_ids(session: Session, account_ids: set[int]) -> list[Account]:
    """按账号 ID 批量查询账号信息。"""
    if not account_ids:
        return []
    statement = select(Account).where(col(Account.id).in_(sorted(account_ids)))
    return list(session.exec(statement).all())
