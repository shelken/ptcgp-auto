# -*- coding: utf-8 -*-
"""通知管理查询。"""

from typing import Optional

from sqlalchemy import String, cast, func, or_
from sqlmodel import Session, col, select

from ptcgp_auto_v2.db.models import Card, CardPack, Notification


SORT_FIELDS = {
    "created_at": col(Notification.created_at),
    "title": col(Notification.title),
    "scene": col(Notification.scene),
}


def normalize_notification_sort(sort_by: str, sort_order: str) -> tuple[str, str]:
    """标准化通知列表排序参数。"""
    normalized_sort_by = sort_by if sort_by in SORT_FIELDS else "created_at"
    normalized_sort_order = "asc" if sort_order == "asc" else "desc"
    return normalized_sort_by, normalized_sort_order


def list_notifications(
    session: Session,
    scene: Optional[str] = None,
    account_id: Optional[int] = None,
    is_read: Optional[bool] = None,
    q: str = "",
    sort_by: str = "created_at",
    sort_order: str = "desc",
    page: int = 0,
    page_size: int = 20,
) -> tuple[list[Notification], int]:
    """查询通知列表并返回分页结果。"""
    normalized_sort_by, normalized_sort_order = normalize_notification_sort(
        sort_by, sort_order
    )
    normalized_page = max(page, 0)
    normalized_page_size = min(max(page_size, 1), 100)

    statement = select(Notification)
    if scene:
        statement = statement.where(Notification.scene == scene)
    if account_id is not None:
        statement = statement.where(Notification.related_account_id == account_id)
    if is_read is not None:
        statement = statement.where(Notification.is_read == is_read)

    q_text = q.strip()
    if q_text:
        statement = statement.where(
            or_(
                col(Notification.title).ilike(f"%{q_text}%"),
                col(Notification.content).ilike(f"%{q_text}%"),
                cast(col(Notification.related_account_id), String).ilike(f"%{q_text}%"),
            )
        )

    sort_column = SORT_FIELDS[normalized_sort_by]
    if normalized_sort_order == "asc":
        statement = statement.order_by(sort_column.asc())
    else:
        statement = statement.order_by(sort_column.desc())

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


def list_recent_notifications(session: Session, limit: int = 5) -> list[Notification]:
    """获取最近通知（按创建时间倒序）。"""
    normalized_limit = min(max(limit, 1), 20)
    statement = (
        select(Notification)
        .order_by(col(Notification.created_at).desc())
        .limit(normalized_limit)
    )
    return list(session.exec(statement).all())


CARD_SORT_FIELDS = {
    "id": col(Card.id),
    "number": col(Card.number),
    "name": col(Card.name),
}


def normalize_card_picker_sort(sort_by: str, sort_order: str) -> tuple[str, str]:
    """标准化卡牌选择器排序参数。"""
    normalized_sort_by = sort_by if sort_by in CARD_SORT_FIELDS else "id"
    normalized_sort_order = "asc" if sort_order == "asc" else "desc"
    return normalized_sort_by, normalized_sort_order


def list_notification_selectable_cards(
    session: Session,
    q: str = "",
    rarity: str = "",
    set_code: str = "",
    pack_name: str = "",
    sort_by: str = "id",
    sort_order: str = "asc",
    page: int = 0,
    page_size: int = 24,
) -> tuple[list[Card], int]:
    """查询通知卡牌选择器数据（严格分页，不允许全量返回）。"""
    normalized_page = max(page, 0)
    normalized_page_size = min(max(page_size, 1), 60)
    normalized_sort_by, normalized_sort_order = normalize_card_picker_sort(
        sort_by, sort_order
    )

    statement = select(Card)
    if pack_name:
        statement = statement.join(CardPack, CardPack.card_id == Card.id).where(
            CardPack.pack_name == pack_name
        )
    if rarity:
        statement = statement.where(Card.rarity == rarity)
    if set_code:
        statement = statement.where(Card.set_code == set_code)

    q_text = q.strip()
    if q_text:
        statement = statement.where(
            or_(
                col(Card.name).ilike(f"%{q_text}%"),
                cast(col(Card.number), String).ilike(f"%{q_text}%"),
                col(Card.set_code).ilike(f"%{q_text}%"),
            )
        )

    statement = statement.distinct()
    sort_column = CARD_SORT_FIELDS[normalized_sort_by]
    if normalized_sort_order == "asc":
        statement = statement.order_by(sort_column.asc())
    else:
        statement = statement.order_by(sort_column.desc())

    total = int(
        session.exec(select(func.count()).select_from(statement.subquery())).one()
    )
    rows = list(
        session.exec(
            statement.offset(normalized_page * normalized_page_size).limit(
                normalized_page_size
            )
        ).all()
    )
    return rows, total
