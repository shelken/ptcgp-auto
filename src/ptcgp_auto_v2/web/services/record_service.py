from typing import Any

from sqlmodel import Session

from ptcgp_auto_v2.db.repositories import CardRepository
from ptcgp_auto_v2.web.queries.record_queries import (
    fetch_records,
    fetch_pack_points_map,
    build_records_next_page_url,
)
from ptcgp_auto_v2.web.utils.form_utils import parse_json_label
from ptcgp_auto_v2.web.utils.i18n import resolve_label


def build_records_list_context(
    *,
    session: Session,
    page: int = 0,
    page_size: int = 10,
    rarity: list[str] | None = None,
    card_type: list[str] | None = None,
) -> dict[str, Any]:
    """构建开包记录列表视图上下文（统一列表协议）。"""
    rarity = rarity or []
    card_type = card_type or []

    results = fetch_records(session, page, page_size, rarity, card_type)

    # 空数据时返回停止标记（用于无限滚动）
    if not results and page > 0:
        return {"stop": True}

    card_repo = CardRepository()
    all_sets = card_repo.get_all_sets()
    all_packs = card_repo.get_all_packs()

    sets_map = {item.code: parse_json_label(item.label_data) for item in all_sets}
    packs_map = {item.name: parse_json_label(item.label_data) for item in all_packs}

    points_map = fetch_pack_points_map(session, results)
    items = []

    for record in results:
        sorted_cards = sorted(record.cards, key=lambda card: card.position)
        card_count = len(sorted_cards)
        layout_type = "layout-3"

        if card_count == 6:
            layout_type = "layout-6"
        elif card_count == 5:
            layout_type = "layout-5"
        elif card_count == 4:
            layout_type = "layout-4"

        current_points = None
        series_code = ""
        if record.pack_code:
            current_points = points_map.get((record.account_id, record.pack_code))
            series_code = record.pack_code
        elif record.pack_type and "/" in record.pack_type:
            series = record.pack_type.split("/")[0]
            current_points = points_map.get((record.account_id, series))
            series_code = series

        set_name_display = series_code
        if series_code in sets_map:
            set_name_display = resolve_label(sets_map[series_code], fallback=series_code)

        pack_name_display = record.pack_name or ""
        if record.pack_name in packs_map:
            pack_name_display = resolve_label(
                packs_map[record.pack_name], fallback=record.pack_name
            )

        items.append(
            {
                "record": record,
                "cards": sorted_cards,
                "layout": layout_type,
                "account_name": record.account.nickname
                if record.account
                else "Unknown",
                "opened_at": record.opened_at,
                "current_points": current_points,
                "series": series_code,
                "set_name_display": set_name_display,
                "pack_name_display": pack_name_display,
            }
        )

    if not items:
        return {"stop": True}

    # 计算分页信息
    # 由于 fetch_records 返回的是固定 page_size 的数据，我们需要判断是否有更多数据
    has_next = len(items) == page_size
    has_prev = page > 0

    return {
        "stop": False,
        "items": items,
        "page": page,
        "page_size": page_size,
        "has_prev": has_prev,
        "has_next": has_next,
    }
