from typing import Iterable

from sqlmodel import Session, select, desc, col

from ptcgp_auto_v2.db.models.pack_record import PackRecord
from ptcgp_auto_v2.db.models.pack_card import PackCard
from ptcgp_auto_v2.db.models.card import Card
from ptcgp_auto_v2.db.models.account_pack_point import AccountPackPoint


def fetch_records(
    session: Session,
    page: int,
    page_size: int,
    rarity: list[str],
    card_type: list[str],
) -> list[PackRecord]:
    """查询开包记录（支持筛选与分页）。"""
    query = select(PackRecord).distinct().order_by(desc(PackRecord.opened_at))

    if rarity or card_type:
        query = query.join(PackRecord.cards).join(PackCard.card)
        if rarity:
            query = query.where(col(Card.rarity).in_(rarity))
        if card_type:
            query = query.where(col(Card.type).in_(card_type))

    offset = page * page_size
    query = query.offset(offset).limit(page_size)
    return list(session.exec(query).all())


def fetch_pack_points_map(
    session: Session, records: Iterable[PackRecord]
) -> dict[tuple[int, str], int]:
    """批量查询账号包点数并构建映射。"""
    target_combinations: set[tuple[int, str]] = set()
    for record in records:
        if record.account_id and record.pack_code:
            target_combinations.add((record.account_id, record.pack_code))

    if not target_combinations:
        return {}

    account_ids = {combo[0] for combo in target_combinations}
    points_stmt = select(AccountPackPoint).where(
        col(AccountPackPoint.account_id).in_(account_ids)
    )
    points_records = session.exec(points_stmt).all()
    points_map: dict[tuple[int, str], int] = {}
    for point in points_records:
        points_map[(point.account_id, point.series)] = point.points
    return points_map


def build_records_next_page_url(
    page: int, lang: str, rarity: list[str], card_type: list[str]
) -> str:
    """构建记录分页 URL。"""
    next_page_url = f"/api/records?page={page + 1}&lang={lang}"
    for item in rarity:
        next_page_url += f"&rarity={item}"
    for item in card_type:
        next_page_url += f"&card_type={item}"
    return next_page_url
