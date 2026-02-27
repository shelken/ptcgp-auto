from typing import Any

from sqlmodel import Session

from ptcgp_auto_v2.db.repositories import CardRepository
from ptcgp_auto_v2.web.queries.record_queries import (
    fetch_records,
    fetch_pack_points_map,
    build_records_next_page_url,
)
from ptcgp_auto_v2.web.utils.form_utils import parse_json_label
from ptcgp_auto_v2.web.utils.i18n import get_current_i18n, resolve_label


def list_records(
    session: Session,
    page: int,
    page_size: int,
    rarity: list[str],
    card_type: list[str],
) -> dict[str, Any]:
    """获取开包记录视图数据。"""
    current_lang, t = get_current_i18n()
    results = fetch_records(session, page, page_size, rarity, card_type)

    if not results and page > 0:
        return {"stop": True}

    card_repo = CardRepository()
    all_sets = card_repo.get_all_sets()
    all_packs = card_repo.get_all_packs()

    sets_map = {item.code: parse_json_label(item.label_data) for item in all_sets}
    packs_map = {item.name: parse_json_label(item.label_data) for item in all_packs}

    points_map = fetch_pack_points_map(session, results)
    records_data = []

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

        records_data.append(
            {
                "record": record,
                "cards": sorted_cards,
                "layout": layout_type,
                "account_name": record.account.nickname
                if record.account
                else t.get("unknown_account", "Unknown"),
                "opened_at": record.opened_at,
                "current_points": current_points,
                "series": series_code,
                "set_name_display": set_name_display,
                "pack_name_display": pack_name_display,
            }
        )

    if not records_data:
        return {"stop": True}

    next_page_url = build_records_next_page_url(page, current_lang, rarity, card_type)

    return {
        "stop": False,
        "records": records_data,
        "next_page_url": next_page_url,
        "t": t,
        "current_lang": current_lang,
    }
