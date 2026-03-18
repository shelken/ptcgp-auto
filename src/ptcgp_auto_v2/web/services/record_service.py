from typing import Any

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
from ptcgp_auto_v2.web.utils.filter_utils import normalize_page, normalize_page_size


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
    batch_ids: list[str],
) -> dict[str, list[PackRecord]]:
    """批量查询批次记录映射。"""
    if not batch_ids:
        return {}
    from ptcgp_auto_v2.db.models.pack_card import PackCard
    from sqlalchemy.orm import selectinload

    stmt = (
        select(PackRecord)
        .where(col(PackRecord.batch_id).in_(batch_ids))
        .options(
            selectinload(PackRecord.cards).selectinload(PackCard.card),
            selectinload(PackRecord.account),
        )
        .order_by(col(PackRecord.batch_id), col(PackRecord.batch_index))
    )
    records = list(session.exec(stmt).all())
    mapping: dict[str, list[PackRecord]] = {}
    for record in records:
        if not record.batch_id:
            continue
        mapping.setdefault(record.batch_id, []).append(record)
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

    return {
        "is_batch": True,
        "batch_id": batch_id,
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


def build_records_list_context(
    *,
    session: Session,
    page: int = 0,
    page_size: int = 10,
    rarity: list[str] | None = None,
    card_type: list[str] | None = None,
) -> dict[str, Any]:
    """构建开包记录列表视图上下文（统一列表协议）。"""
    normalized_page = normalize_page(page)
    normalized_page_size = normalize_page_size(page_size)
    rarity = rarity or []
    card_type = card_type or []

    results, has_next = fetch_display_entity_records(
        session,
        normalized_page,
        normalized_page_size,
        rarity,
        card_type,
    )

    card_repo = CardRepository(session)
    set_codes = sorted({record.set_code for record in results if record.set_code})
    pack_names = sorted({record.pack_name for record in results if record.pack_name})
    sets_map = {
        code: parse_json_label(label_data)
        for code, label_data in card_repo.get_set_labels_map(set_codes).items()
    }
    packs_map = {
        pack_name: parse_json_label(label_data)
        for pack_name, label_data in card_repo.get_pack_labels_map(pack_names).items()
    }

    points_map = fetch_pack_points_map(session, results)
    items = []
    _, translations = get_current_i18n()
    batch_record_map = _fetch_batch_records_map(
        session,
        sorted({record.batch_id for record in results if record.batch_id}),
    )

    # 用于追踪已处理的批次，避免重复展示
    processed_batches: set[str] = set()

    for record in results:
        # 十连包批次处理：只处理每批的第一条记录，聚合整批
        if (
            record.pack_type == PackRecordType.TEN_PACK
            and record.batch_id
            and record.batch_id not in processed_batches
        ):
            processed_batches.add(record.batch_id)

            batch_records = batch_record_map.get(record.batch_id, [])
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

        # 十连包的后续记录（同一批次的非第一条）跳过
        if record.pack_type == PackRecordType.TEN_PACK and record.batch_id:
            continue

        # 单包处理（保持原有逻辑）
        sorted_cards = sorted(record.cards, key=lambda card: card.position)
        card_views = [_build_record_card_view(card) for card in sorted_cards]
        card_count = len(card_views)
        layout_type = "layout-3"

        if card_count == 6:
            layout_type = "layout-6"
        elif card_count == 5:
            layout_type = "layout-5"
        elif card_count == 4:
            layout_type = "layout-4"

        current_points = None
        series_code = ""
        if record.set_code:
            current_points = points_map.get((record.account_id, record.set_code))
            series_code = record.set_code
        elif record.pack_type and "/" in record.pack_type:
            parts = record.pack_type.split("/")
            if parts:
                series = parts[0]
                current_points = points_map.get((record.account_id, series))
                series_code = series

        set_name_display = series_code
        if series_code in sets_map:
            set_name_display = resolve_label(
                sets_map[series_code], fallback=series_code
            )

        pack_name_display = record.pack_name or ""
        if record.pack_name in packs_map:
            pack_name_display = resolve_label(
                packs_map[record.pack_name], fallback=record.pack_name
            )
        pack_type_display = str(
            translations.get(record.pack_type, record.pack_type or "")
        )

        items.append(
            {
                "is_batch": False,
                "record": record,
                "cards": card_views,
                "layout": layout_type,
                "account_name": (
                    record.account.nickname if record.account else "Unknown"
                ),
                "opened_at": record.opened_at,
                "current_points": current_points,
                "series": series_code,
                "set_name_display": set_name_display,
                "pack_name_display": pack_name_display,
                "pack_type_display": pack_type_display,
            }
        )

    return {
        "items": items,
        "page": normalized_page,
        "page_size": normalized_page_size,
        "has_prev": normalized_page > 0,
        "has_next": has_next,
        "total": (normalized_page * normalized_page_size)
        + len(items)
        + (normalized_page_size if has_next else 0),
    }
