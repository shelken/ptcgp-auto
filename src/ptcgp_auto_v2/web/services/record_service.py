from dataclasses import dataclass
from typing import Any

from sqlalchemy import tuple_
from sqlmodel import Session, select, col

from ptcgp_auto_v2.config.rarity_icons import RARITY_META
from ptcgp_auto_v2.db.repositories import CardRepository
from ptcgp_auto_v2.db.models.pack_record import PackRecord, PackRecordType
from ptcgp_auto_v2.web.queries.record_queries import (
    fetch_display_entity_records,
    fetch_pack_points_map,
)
from ptcgp_auto_v2.web.utils.form_utils import parse_json_label
from ptcgp_auto_v2.web.utils.i18n import (
    get_current_i18n,
    resolve_label,
    resolve_card_name_from_data,
)
from ptcgp_auto_v2.web.utils.filter_utils import (
    normalize_page,
    normalize_page_size,
    normalize_query_text,
)

BatchKey = tuple[int, str]


@dataclass(frozen=True)
class RecordsListQueryState:
    """统一开包记录查询状态，减少路由与服务层重复解析。"""

    page: int
    page_size: int
    rarity: list[str]
    card_type: list[str]
    set_code: list[str]
    card_name_query: str


def _normalize_records_filter_values(values: list[str] | None) -> list[str]:
    """归一化多选筛选项，统一去空白与空字符串。"""
    if not values:
        return []
    return [item.strip() for item in values if item and item.strip()]


def build_records_list_query_state(
    *,
    page: int = 0,
    page_size: int = 10,
    rarity: list[str] | None = None,
    card_type: list[str] | None = None,
    set_code: list[str] | None = None,
    card_name_query: str = "",
    max_page_size: int = 100,
) -> RecordsListQueryState:
    """构建 records 列表统一查询状态。"""
    return RecordsListQueryState(
        page=normalize_page(page),
        page_size=normalize_page_size(page_size, max_size=max_page_size),
        rarity=_normalize_records_filter_values(rarity),
        card_type=_normalize_records_filter_values(card_type),
        set_code=_normalize_records_filter_values(set_code),
        card_name_query=normalize_query_text(card_name_query),
    )


def _resolve_record_card_name(pack_card: Any) -> str:
    """解析开包记录中的卡牌展示名（优先当前语言本地化）。"""
    card = getattr(pack_card, "card", None)
    fallback_name = str(getattr(pack_card, "card_name", "") or "")
    if card is None:
        return fallback_name
    return resolve_card_name_from_data(card.data, fallback=fallback_name or card.name)


def _build_record_card_view(pack_card: Any) -> dict[str, Any]:
    """构建记录页卡牌视图模型，避免直接给 ORM 模型动态加字段。"""
    return {
        "display_name": _resolve_record_card_name(pack_card),
        "card_name": str(getattr(pack_card, "card_name", "") or ""),
        "rarity": str(getattr(pack_card, "rarity", "") or ""),
        "is_new": bool(getattr(pack_card, "is_new", False)),
        "position": int(getattr(pack_card, "position", 0) or 0),
        "card": getattr(pack_card, "card", None),
    }


def _fetch_batch_records_map(
    session: Session,
    batch_keys: list[BatchKey],
) -> dict[BatchKey, list[PackRecord]]:
    """批量查询批次记录映射。"""
    if not batch_keys:
        return {}
    from ptcgp_auto_v2.db.models.pack_card import PackCard
    from sqlalchemy.orm import selectinload

    stmt = (
        select(PackRecord)
        .where(tuple_(col(PackRecord.account_id), col(PackRecord.batch_id)).in_(batch_keys))
        .options(
            selectinload(PackRecord.cards).selectinload(PackCard.card),
            selectinload(PackRecord.account),
        )
        .order_by(col(PackRecord.account_id), col(PackRecord.batch_id), col(PackRecord.batch_index))
    )
    records = list(session.exec(stmt).all())
    mapping: dict[BatchKey, list[PackRecord]] = {}
    for record in records:
        if not record.batch_id:
            continue
        # 变更原因：生产数据中不同账号可能生成相同 batch_id，批次明细必须按账号隔离。
        mapping.setdefault((record.account_id, record.batch_id), []).append(record)
    return mapping


def _build_batch_pack_view(
    record: PackRecord,
    card_views: list[dict[str, Any]],
) -> dict[str, Any]:
    """构建十连包中单个包的视图（用于概览展示）。"""
    # 找出最高稀有度的卡牌作为封面
    cover_card = None
    max_rarity = ""
    max_weight = -1
    has_new = False

    for card in card_views:
        rarity = card.get("rarity", "")
        meta = RARITY_META.get(rarity)
        weight = meta["priority"] if meta else -1
        if weight > max_weight:
            max_weight = weight
            max_rarity = rarity
            cover_card = card
        if card.get("is_new"):
            has_new = True

    # 如果没有找到封面（空包），取第一张
    if cover_card is None and card_views:
        cover_card = card_views[0]
        max_rarity = cover_card.get("rarity", "")

    return {
        "record": record,
        "batch_index": record.batch_index,
        "cards": card_views,
        "cover_card": cover_card,
        "max_rarity": max_rarity,
        "has_new": has_new,
        "card_count": len(card_views),
    }


def _build_batch_item_view(
    batch_id: str,
    batch_records: list[PackRecord],
    points_map: dict[tuple[int, str], int],
    sets_map: dict[str, dict[str, Any]],
    packs_map: dict[str, dict[str, Any]],
    translations: dict[str, Any],
) -> dict[str, Any]:
    """构建十连批次整卡视图模型。"""
    batch_packs = []
    total_cards = 0
    for pack in batch_records:
        sorted_cards = sorted(pack.cards, key=lambda c: c.position)
        card_views = [_build_record_card_view(c) for c in sorted_cards]
        batch_packs.append(_build_batch_pack_view(pack, card_views))
        total_cards += len(card_views)

    first_pack = batch_records[0]
    series_code = first_pack.set_code or ""
    current_points = None
    if series_code:
        current_points = points_map.get((first_pack.account_id, series_code))

    set_name_display = series_code
    if series_code in sets_map:
        set_name_display = resolve_label(sets_map[series_code], fallback=series_code)

    pack_name_display = first_pack.pack_name or ""
    if first_pack.pack_name in packs_map:
        pack_name_display = resolve_label(
            packs_map[first_pack.pack_name], fallback=first_pack.pack_name
        )

    batch_key = f"{first_pack.account_id}:{batch_id}"

    return {
        "is_batch": True,
        # 变更原因：前端十连包展开状态必须区分不同账号下相同 batch_id。
        "batch_key": batch_key,
        "batch_id": batch_id,
        "account_id": first_pack.account_id,
        "batch_packs": batch_packs,
        "total_cards": total_cards,
        "record": first_pack,
        "account_name": first_pack.account.nickname
        if first_pack.account
        else "Unknown",
        "opened_at": first_pack.opened_at,
        "current_points": current_points,
        "series": series_code,
        "set_name_display": set_name_display,
        "pack_name_display": pack_name_display,
        "pack_type_display": str(translations.get(PackRecordType.TEN_PACK, "十连开包")),
    }


def _build_label_maps(
    card_repo: CardRepository,
    records: list[PackRecord],
) -> tuple[dict[str, dict[str, Any]], dict[str, dict[str, Any]]]:
    """批量构建系列和卡包标签映射。"""
    set_codes = sorted({record.set_code for record in records if record.set_code})
    pack_names = sorted({record.pack_name for record in records if record.pack_name})
    sets_map = {
        code: parse_json_label(label_data)
        for code, label_data in card_repo.get_set_labels_map(set_codes).items()
    }
    packs_map = {
        pack_name: parse_json_label(label_data)
        for pack_name, label_data in card_repo.get_pack_labels_map(pack_names).items()
    }
    return sets_map, packs_map


def _resolve_single_layout(card_count: int) -> str:
    """按卡牌数量返回布局类型。"""
    if card_count == 6:
        return "layout-6"
    if card_count == 5:
        return "layout-5"
    if card_count == 4:
        return "layout-4"
    return "layout-3"


def _resolve_series_and_points(
    record: PackRecord,
    points_map: dict[tuple[int, str], int],
) -> tuple[str, int | None]:
    """解析记录所属系列和点数。"""
    current_points = None
    series_code = ""
    if record.set_code:
        series_code = record.set_code
        current_points = points_map.get((record.account_id, record.set_code))
        return series_code, current_points

    if record.pack_type and "/" in record.pack_type:
        parts = record.pack_type.split("/")
        if parts:
            series_code = parts[0]
            current_points = points_map.get((record.account_id, series_code))
    return series_code, current_points


def _build_single_item_view(
    record: PackRecord,
    points_map: dict[tuple[int, str], int],
    sets_map: dict[str, dict[str, Any]],
    packs_map: dict[str, dict[str, Any]],
    translations: dict[str, Any],
) -> dict[str, Any]:
    """构建单包记录视图。"""
    sorted_cards = sorted(record.cards, key=lambda card: card.position)
    card_views = [_build_record_card_view(card) for card in sorted_cards]
    series_code, current_points = _resolve_series_and_points(record, points_map)

    set_name_display = series_code
    if series_code in sets_map:
        set_name_display = resolve_label(sets_map[series_code], fallback=series_code)

    pack_name_display = record.pack_name or ""
    if record.pack_name in packs_map:
        pack_name_display = resolve_label(
            packs_map[record.pack_name], fallback=record.pack_name
        )

    pack_type_display = str(
        translations.get(record.pack_type, record.pack_type or "")
    )
    return {
        "is_batch": False,
        "record": record,
        "cards": card_views,
        "layout": _resolve_single_layout(len(card_views)),
        "account_name": (record.account.nickname if record.account else "Unknown"),
        "opened_at": record.opened_at,
        "current_points": current_points,
        "series": series_code,
        "set_name_display": set_name_display,
        "pack_name_display": pack_name_display,
        "pack_type_display": pack_type_display,
    }


def _build_record_items(
    *,
    results: list[PackRecord],
    batch_record_map: dict[BatchKey, list[PackRecord]],
    points_map: dict[tuple[int, str], int],
    sets_map: dict[str, dict[str, Any]],
    packs_map: dict[str, dict[str, Any]],
    translations: dict[str, Any],
) -> list[dict[str, Any]]:
    """按展示规则构建记录列表项（十连聚合 + 单包）。"""
    items: list[dict[str, Any]] = []
    processed_batches: set[BatchKey] = set()
    for record in results:
        if record.pack_type == PackRecordType.TEN_PACK and record.batch_id:
            batch_key = (record.account_id, record.batch_id)
            if batch_key in processed_batches:
                continue
            processed_batches.add(batch_key)
            batch_records = batch_record_map.get(batch_key, [])
            items.append(
                _build_batch_item_view(
                    batch_id=record.batch_id,
                    batch_records=batch_records,
                    points_map=points_map,
                    sets_map=sets_map,
                    packs_map=packs_map,
                    translations=translations,
                )
            )
            continue

        items.append(
            _build_single_item_view(
                record=record,
                points_map=points_map,
                sets_map=sets_map,
                packs_map=packs_map,
                translations=translations,
            )
        )
    return items


def build_records_list_context(
    *,
    session: Session,
    page: int = 0,
    page_size: int = 10,
    rarity: list[str] | None = None,
    card_type: list[str] | None = None,
    set_code: list[str] | None = None,
    card_name_query: str = "",
) -> dict[str, Any]:
    """构建开包记录列表视图上下文（统一列表协议）。"""
    list_state = build_records_list_query_state(
        page=page,
        page_size=page_size,
        rarity=rarity,
        card_type=card_type,
        set_code=set_code,
        card_name_query=card_name_query,
    )

    results, has_next = fetch_display_entity_records(
        session,
        list_state.page,
        list_state.page_size,
        list_state.rarity,
        list_state.card_type,
        list_state.set_code,
        list_state.card_name_query,
    )

    card_repo = CardRepository(session)
    sets_map, packs_map = _build_label_maps(card_repo, results)
    points_map = fetch_pack_points_map(session, results)
    _, translations = get_current_i18n()
    batch_record_map = _fetch_batch_records_map(
        session,
        sorted({(record.account_id, record.batch_id) for record in results if record.batch_id}),
    )
    items = _build_record_items(
        results=results,
        batch_record_map=batch_record_map,
        points_map=points_map,
        sets_map=sets_map,
        packs_map=packs_map,
        translations=translations,
    )

    return {
        "items": items,
        "page": list_state.page,
        "page_size": list_state.page_size,
        "has_prev": list_state.page > 0,
        "has_next": has_next,
        "total": (list_state.page * list_state.page_size)
        + len(items)
        + (list_state.page_size if has_next else 0),
    }
