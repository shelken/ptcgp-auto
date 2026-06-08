from typing import Iterable

from sqlmodel import Session, select, desc, col
from sqlalchemy import String, cast, func, literal, or_, tuple_, union_all
from sqlalchemy.orm import selectinload

from ptcgp_auto_v2.db.models.pack_record import PackRecord, PackRecordType
from ptcgp_auto_v2.db.models.pack_card import PackCard
from ptcgp_auto_v2.db.models.card import Card
from ptcgp_auto_v2.db.models.account_pack_point import AccountPackPoint
from ptcgp_auto_v2.web.queries._query_helpers import (
    fetch_window_rows,
    normalize_pagination,
)

# 展示实体类型标识（用于记录分页的实体键类型）
DISPLAY_ENTITY_TYPE_TEN_PACK = "ten_pack"
DISPLAY_ENTITY_TYPE_SINGLE = "single"


def _apply_pack_record_filters(
    query,
    rarity: list[str],
    card_type: list[str],
    set_code: list[str],
    card_name_query: str,
):
    """按开包记录筛选条件追加查询条件。"""
    if set_code:
        query = query.where(col(PackRecord.pack_code).in_(set_code))

    if rarity or card_type or card_name_query:
        query = query.join(PackRecord.cards).join(PackCard.card)
        if rarity:
            query = query.where(col(Card.rarity).in_(rarity))
        if card_type:
            query = query.where(col(Card.type).in_(card_type))
        if card_name_query:
            like_value = f"%{card_name_query}%"
            query = query.where(
                or_(
                    col(PackCard.card_name).ilike(like_value),
                    col(Card.name).ilike(like_value),
                    cast(col(Card.data), String).ilike(like_value),
                )
            )
    return query

def fetch_display_entity_records(
    session: Session,
    page: int,
    page_size: int,
    rarity: list[str],
    card_type: list[str],
    set_code: list[str],
    card_name_query: str,
) -> tuple[list[PackRecord], bool]:
    """按展示实体分页查询开包记录（十连包按批次聚合）。"""
    normalized_page, normalized_page_size = normalize_pagination(
        page=page,
        page_size=page_size,
        max_size=100,
    )
    # 处理流程：按展示实体键分页 -> 回查代表记录 -> 按实体顺序重建结果列表
    ten_pack_stmt = (
        select(
            literal(DISPLAY_ENTITY_TYPE_TEN_PACK).label("entity_type"),
            col(PackRecord.account_id).label("account_id"),
            cast(col(PackRecord.batch_id), String).label("entity_key"),
            func.max(col(PackRecord.opened_at)).label("sort_time"),
            # 变更原因：十连批次同 sort_time 时需要稳定批次代表 ID 做分页 tie-breaker。
            func.max(col(PackRecord.id)).label("sort_id"),
        )
        .where(col(PackRecord.pack_type) == PackRecordType.TEN_PACK)
        .where(col(PackRecord.batch_id).is_not(None))
    )
    ten_pack_stmt = _apply_pack_record_filters(
        ten_pack_stmt, rarity, card_type, set_code, card_name_query
    )
    ten_pack_stmt = ten_pack_stmt.group_by(col(PackRecord.account_id), col(PackRecord.batch_id))

    single_stmt = select(
        literal(DISPLAY_ENTITY_TYPE_SINGLE).label("entity_type"),
        col(PackRecord.account_id).label("account_id"),
        cast(col(PackRecord.id), String).label("entity_key"),
        col(PackRecord.opened_at).label("sort_time"),
        col(PackRecord.id).label("sort_id"),
    ).where(col(PackRecord.pack_type) != PackRecordType.TEN_PACK)
    single_stmt = _apply_pack_record_filters(
        single_stmt, rarity, card_type, set_code, card_name_query
    )
    single_stmt = single_stmt.group_by(
        col(PackRecord.id), col(PackRecord.account_id), col(PackRecord.opened_at)
    )

    entity_stmt = union_all(ten_pack_stmt, single_stmt).subquery()

    page_stmt = (
        select(
            entity_stmt.c.entity_type,
            entity_stmt.c.account_id,
            entity_stmt.c.entity_key,
            entity_stmt.c.sort_time,
            entity_stmt.c.sort_id,
        )
        .order_by(desc(entity_stmt.c.sort_time), desc(entity_stmt.c.sort_id))
    )
    rows, has_next = fetch_window_rows(
        session=session,
        statement=page_stmt,
        page=normalized_page,
        page_size=normalized_page_size,
    )
    if not rows:
        return [], False

    entity_order: list[tuple[str, int, str]] = [(row[0], row[1], row[2]) for row in rows]
    single_ids = [int(row[2]) for row in rows if row[0] == DISPLAY_ENTITY_TYPE_SINGLE]
    ten_batch_pairs = [(row[1], row[2]) for row in rows if row[0] == DISPLAY_ENTITY_TYPE_TEN_PACK]
    record_ids: list[int] = list(single_ids)

    if ten_batch_pairs:
        ten_records_stmt = (
            select(
                col(PackRecord.id).label("record_id"),
                col(PackRecord.account_id).label("account_id"),
                col(PackRecord.batch_id).label("batch_id"),
                func.row_number()
                .over(
                    partition_by=(col(PackRecord.account_id), col(PackRecord.batch_id)),
                    order_by=(
                        desc(col(PackRecord.opened_at)),
                        desc(col(PackRecord.id)),
                    ),
                )
                .label("row_num"),
            )
            .where(col(PackRecord.pack_type) == PackRecordType.TEN_PACK)
            .where(tuple_(col(PackRecord.account_id), col(PackRecord.batch_id)).in_(ten_batch_pairs))
        )
        ten_records_stmt = _apply_pack_record_filters(
            ten_records_stmt, rarity, card_type, set_code, card_name_query
        )
        ten_records_subquery = ten_records_stmt.subquery()
        ten_ids_stmt = select(ten_records_subquery.c.record_id).where(
            ten_records_subquery.c.row_num == 1
        )
        record_ids.extend(session.exec(ten_ids_stmt).all())

    if not record_ids:
        return [], False

    records_stmt = (
        select(PackRecord)
        .options(
            selectinload(PackRecord.cards).selectinload(PackCard.card),
            selectinload(PackRecord.account),
        )
        .where(col(PackRecord.id).in_(record_ids))
    )
    records = list(session.exec(records_stmt).all())

    records_map: dict[tuple[str, int, str], PackRecord] = {}
    for record in records:
        if record.pack_type == PackRecordType.TEN_PACK and record.batch_id:
            # 变更原因：同一 batch_id 可能出现在多个账号，展示实体必须按账号隔离。
            key = (DISPLAY_ENTITY_TYPE_TEN_PACK, record.account_id, record.batch_id)
        else:
            key = (DISPLAY_ENTITY_TYPE_SINGLE, record.account_id, str(record.id))
        records_map[key] = record

    ordered_records = [records_map[key] for key in entity_order if key in records_map]
    return ordered_records, has_next


def fetch_pack_points_map(
    session: Session, records: Iterable[PackRecord]
) -> dict[tuple[int, str], int]:
    """批量查询账号包点数并构建映射。"""
    target_combinations: set[tuple[int, str]] = set()
    for record in records:
        series_code = record.set_code
        if not series_code and record.pack_type and "/" in record.pack_type:
            # 变更原因：旧格式记录只把系列写在 pack_type 前缀，包点查询必须与展示解析一致。
            series_code = record.pack_type.split("/", 1)[0]
        if record.account_id and series_code:
            target_combinations.add((record.account_id, series_code))

    if not target_combinations:
        return {}

    points_stmt = select(AccountPackPoint).where(
        # 变更原因：当前页只需要这些账号-系列组合，避免把同账号其它系列包点混入结果。
        tuple_(col(AccountPackPoint.account_id), col(AccountPackPoint.series)).in_(
            target_combinations
        )
    )
    points_records = session.exec(points_stmt).all()
    points_map: dict[tuple[int, str], int] = {}
    for point in points_records:
        points_map[(point.account_id, point.series)] = point.points
    return points_map
