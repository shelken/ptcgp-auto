# -*- coding: utf-8 -*-
"""
每日送卡管理页面服务。

负责组装统计、配对互送进度和送卡记录三个独立区块。
"""

from datetime import datetime, timedelta
from typing import Any

from sqlmodel import Session

from ptcgp_auto_v2.db.models import AccountGiftPair, AccountGiftRecord
from ptcgp_auto_v2.utils.game_time import get_game_biz_date_str
from ptcgp_auto_v2.web.queries.daily_gift_queries import (
    fetch_daily_gift_records_page,
    fetch_daily_gift_stats,
    list_active_gift_pairs,
    list_all_accounts,
    list_daily_gift_pair_records,
)
from ptcgp_auto_v2.web.utils.filter_utils import normalize_page, normalize_page_size


def _today_local_date() -> str:
    """返回游戏业务日期 YYYY-MM-DD。"""
    return get_game_biz_date_str()


def _normalize_biz_date_local(raw_date: str | None) -> str:
    """规范化业务日期，非法输入自动回退到今天。"""
    if not raw_date:
        return _today_local_date()
    value = str(raw_date).strip()
    try:
        return datetime.strptime(value, "%Y-%m-%d").strftime("%Y-%m-%d")
    except ValueError:
        return _today_local_date()


def _build_recent_dates(center_date: str, days: int = 6) -> list[str]:
    """构建最近日期选项，包含当天向前回溯 days 天。"""
    start = datetime.strptime(center_date, "%Y-%m-%d")
    return [
        (start - timedelta(days=offset)).strftime("%Y-%m-%d")
        for offset in range(0, max(days, 0) + 1)
    ]


def _format_card_label(card_set_code: str | None, card_number: int | None) -> str:
    """格式化送出卡牌展示标签。"""
    if not card_set_code and card_number is None:
        return "-"
    if not card_set_code:
        return str(card_number)
    if card_number is None:
        return card_set_code
    return f"{card_set_code}-{card_number}"


def _build_pair_cards(
    pairs: list[AccountGiftPair],
    account_name_map: dict[int, str],
) -> list[dict[str, Any]]:
    """将双向配对关系合并为唯一配对卡片。"""
    pair_by_account_id: dict[int, AccountGiftPair] = {}
    for row in pairs:
        if row.account_id not in pair_by_account_id:
            pair_by_account_id[row.account_id] = row

    merged_pair_keys: set[tuple[int, int]] = set()
    pair_cards: list[dict[str, Any]] = []

    for row in pairs:
        account_id = row.account_id
        target_account_id = row.target_account_id
        if not isinstance(target_account_id, int):
            continue

        reverse = pair_by_account_id.get(target_account_id)
        if reverse is None or reverse.target_account_id != account_id:
            continue

        pair_key = (
            (account_id, target_account_id)
            if account_id <= target_account_id
            else (target_account_id, account_id)
        )
        if pair_key in merged_pair_keys:
            continue

        left_account_id, right_account_id = pair_key
        pair_cards.append(
            {
                "left_account_id": left_account_id,
                "right_account_id": right_account_id,
                "left_name": account_name_map.get(
                    left_account_id, f"#{left_account_id}"
                ),
                "right_name": account_name_map.get(
                    right_account_id, f"#{right_account_id}"
                ),
            }
        )
        merged_pair_keys.add(pair_key)

    pair_cards.sort(
        key=lambda item: (item["left_account_id"], item["right_account_id"])
    )
    return pair_cards


def _build_pair_send_status_rows(
    records: list[AccountGiftRecord],
    pair_cards: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """按配对关系聚合当日互送状态。"""
    latest_record_map: dict[tuple[int, int], AccountGiftRecord] = {}
    for row in records:
        if not isinstance(row.target_account_id, int):
            continue
        pair_key = (row.account_id, int(row.target_account_id))
        if pair_key not in latest_record_map:
            latest_record_map[pair_key] = row

    rows: list[dict[str, Any]] = []
    for pair in pair_cards:
        left_id = int(pair["left_account_id"])
        right_id = int(pair["right_account_id"])

        left_to_right = latest_record_map.get((left_id, right_id))
        right_to_left = latest_record_map.get((right_id, left_id))

        left_status = left_to_right.status if left_to_right else "not_sent"
        right_status = right_to_left.status if right_to_left else "not_sent"
        has_failure = left_status == "failed" or right_status == "failed"

        if left_status == "success" and right_status == "success":
            pair_progress = "mutual_success"
        elif left_status == "success" or right_status == "success":
            pair_progress = "single_success"
        elif left_status == "not_sent" and right_status == "not_sent":
            pair_progress = "none_sent"
        elif has_failure:
            pair_progress = "has_failure"
        else:
            pair_progress = "in_progress"

        rows.append(
            {
                "left_account_id": left_id,
                "right_account_id": right_id,
                "left_name": pair["left_name"],
                "right_name": pair["right_name"],
                "left_to_right_status": left_status,
                "right_to_left_status": right_status,
                "left_to_right_error": left_to_right.error_code if left_to_right else None,
                "right_to_left_error": right_to_left.error_code
                if right_to_left
                else None,
                "pair_progress": pair_progress,
            }
        )

    return rows


def _paginate_rows(
    rows: list[dict[str, Any]],
    *,
    page: int,
    page_size: int,
) -> tuple[list[dict[str, Any]], bool, bool, int]:
    """对内存中的行数据做统一分页。"""
    total = len(rows)
    start = page * page_size
    end = start + page_size
    return rows[start:end], page > 0, end < total, total


def _build_record_rows(
    records: list[AccountGiftRecord],
    account_name_map: dict[int, str],
) -> list[dict[str, Any]]:
    """构建送卡记录展示行。"""
    rows: list[dict[str, Any]] = []
    for row in records:
        target_name = "-"
        if isinstance(row.target_account_id, int):
            target_name = account_name_map.get(row.target_account_id, "-")

        rows.append(
            {
                "id": row.id,
                "account_id": row.account_id,
                "account_name": account_name_map.get(row.account_id, f"#{row.account_id}"),
                "target_account_id": row.target_account_id,
                "target_name": target_name,
                "target_friend_id": row.target_friend_id,
                "card_label": _format_card_label(row.card_set_code, row.card_number),
                "status": row.status,
                "before_count": row.before_count,
                "after_count": row.after_count,
                "error_code": row.error_code,
                "error_message": row.error_message,
                "updated_at": row.updated_at,
            }
        )
    return rows


def build_daily_gift_context(
    session: Session,
    biz_date_local: str | None = None,
    account_id: int | None = None,
    sort_by: str = "updated_at",
    sort_order: str = "desc",
    page: int = 0,
    page_size: int = 10,
    pair_page: int = 0,
    pair_page_size: int = 10,
) -> dict[str, Any]:
    """构建每日送卡页面上下文。"""
    selected_date = _normalize_biz_date_local(biz_date_local)
    current_biz_date_local = _today_local_date()

    normalized_page = normalize_page(page)
    normalized_page_size = normalize_page_size(page_size)
    normalized_pair_page = normalize_page(pair_page)
    normalized_pair_page_size = normalize_page_size(pair_page_size)

    accounts = list_all_accounts(session=session)
    account_name_map = {
        account.id: account.display_name
        for account in accounts
        if isinstance(account.id, int)
    }

    stats = fetch_daily_gift_stats(
        session=session,
        biz_date_local=selected_date,
        account_id=account_id,
    )
    paged_records, has_next, records_total = fetch_daily_gift_records_page(
        session=session,
        biz_date_local=selected_date,
        account_id=account_id,
        sort_by=sort_by,
        sort_order=sort_order,
        page=normalized_page,
        page_size=normalized_page_size,
    )

    active_pairs = list_active_gift_pairs(session=session, account_id=account_id)
    pair_cards = _build_pair_cards(
        pairs=active_pairs,
        account_name_map=account_name_map,
    )
    pair_records = list_daily_gift_pair_records(
        session=session,
        biz_date_local=selected_date,
        account_id=account_id,
    )
    pair_send_status_rows_all = _build_pair_send_status_rows(
        records=pair_records,
        pair_cards=pair_cards,
    )
    pair_send_status_rows, pair_has_prev, pair_has_next, pair_total = _paginate_rows(
        pair_send_status_rows_all,
        page=normalized_pair_page,
        page_size=normalized_pair_page_size,
    )

    return {
        "accounts": accounts,
        "account_name_map": account_name_map,
        "selected_account_id": account_id,
        "records": _build_record_rows(
            records=paged_records,
            account_name_map=account_name_map,
        ),
        "records_total": records_total,
        "page": normalized_page,
        "page_size": normalized_page_size,
        "has_prev": normalized_page > 0,
        "has_next": has_next,
        "sort_by": sort_by,
        "sort_order": sort_order,
        "pair_send_status_rows": pair_send_status_rows,
        "pair_total": pair_total,
        "pair_page": normalized_pair_page,
        "pair_page_size": normalized_pair_page_size,
        "pair_has_prev": pair_has_prev,
        "pair_has_next": pair_has_next,
        "stats": stats,
        "selected_biz_date_local": selected_date,
        "current_biz_date_local": current_biz_date_local,
        "recent_biz_dates": _build_recent_dates(selected_date),
    }
