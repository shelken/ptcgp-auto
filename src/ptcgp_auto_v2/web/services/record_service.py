from typing import Any

from sqlmodel import Session

from ptcgp_auto_v2.db.repositories import CardRepository
from ptcgp_auto_v2.web.queries.record_queries import (
    fetch_records,
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

    results, has_next = fetch_records(
        session,
        normalized_page,
        normalized_page_size,
        rarity,
        card_type,
    )

    card_repo = CardRepository()
    all_sets = card_repo.get_all_sets()
    all_packs = card_repo.get_all_packs()

    sets_map = {item.code: parse_json_label(item.label_data) for item in all_sets}
    packs_map = {item.name: parse_json_label(item.label_data) for item in all_packs}

    points_map = fetch_pack_points_map(session, results)
    items = []
    _, translations = get_current_i18n()

    for record in results:
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
            series = record.pack_type.split("/")[0]
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
                "record": record,
                "cards": card_views,
                "layout": layout_type,
                "account_name": record.account.nickname
                if record.account
                else "Unknown",
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
