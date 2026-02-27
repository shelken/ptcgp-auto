# -*- coding: utf-8 -*-
"""
每日送卡管理页面服务。

负责组装送卡执行视图与配对可视化数据，强调“谁和谁配对”的直观展示。
"""

from datetime import datetime, timedelta
from typing import Any

from sqlmodel import Session

from ptcgp_auto_v2.db.models import AccountGiftPair
from ptcgp_auto_v2.utils.game_time import get_game_biz_date_str
from ptcgp_auto_v2.web.queries.daily_gift_queries import (
    list_accounts_by_ids,
    list_active_gift_pairs,
    list_daily_gift_records,
)
from ptcgp_auto_v2.web.utils.i18n import get_current_i18n


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


def _build_pair_views(
    pairs: list[AccountGiftPair],
    account_name_map: dict[int, str],
    account_friend_id_map: dict[int, str],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """将单向配对记录合并为双向卡片，并提取异常关系。"""
    pair_by_account_id: dict[int, AccountGiftPair] = {}
    for row in pairs:
        if row.account_id not in pair_by_account_id:
            pair_by_account_id[row.account_id] = row

    merged_pair_keys: set[tuple[int, int]] = set()
    pair_cards: list[dict[str, Any]] = []
    anomalies: list[dict[str, Any]] = []

    for row in pairs:
        account_id = row.account_id
        target_account_id = row.target_account_id

        if not isinstance(target_account_id, int):
            anomalies.append(
                {
                    "account_id": account_id,
                    "target_account_id": None,
                    "account_name": account_name_map.get(account_id, f"#{account_id}"),
                    "target_name": "-",
                    "account_friend_id": account_friend_id_map.get(account_id, "-"),
                    "target_friend_id": row.target_friend_id or "-",
                    "reason_code": "target_account_missing",
                }
            )
            continue

        target_id = int(target_account_id)
        pair_key: tuple[int, int] = (
            (account_id, target_id)
            if account_id <= target_id
            else (target_id, account_id)
        )
        if pair_key in merged_pair_keys:
            continue

        reverse = pair_by_account_id.get(target_id)
        if reverse is None:
            anomalies.append(
                {
                    "account_id": account_id,
                    "target_account_id": target_id,
                    "account_name": account_name_map.get(account_id, f"#{account_id}"),
                    "target_name": account_name_map.get(target_id, f"#{target_id}"),
                    "account_friend_id": account_friend_id_map.get(account_id, "-"),
                    "target_friend_id": row.target_friend_id or "-",
                    "reason_code": "single_direction",
                }
            )
            continue

        if reverse.target_account_id != account_id:
            anomalies.append(
                {
                    "account_id": account_id,
                    "target_account_id": target_id,
                    "account_name": account_name_map.get(account_id, f"#{account_id}"),
                    "target_name": account_name_map.get(target_id, f"#{target_id}"),
                    "account_friend_id": account_friend_id_map.get(account_id, "-"),
                    "target_friend_id": row.target_friend_id or "-",
                    "reason_code": "reverse_mismatch",
                }
            )
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
                "left_friend_id": account_friend_id_map.get(left_account_id, "-"),
                "right_friend_id": account_friend_id_map.get(right_account_id, "-"),
            }
        )
        merged_pair_keys.add(pair_key)

    pair_cards.sort(
        key=lambda item: (item["left_account_id"], item["right_account_id"])
    )
    anomalies.sort(
        key=lambda item: (
            item["reason_code"],
            item["account_id"],
            item["target_account_id"] or 0,
        )
    )
    return pair_cards, anomalies


def _build_pair_send_status_rows(
    records: list[dict[str, Any]],
    pair_cards: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """按配对关系聚合当日互送状态，便于直观看双向进度。"""
    latest_record_map: dict[tuple[int, int], dict[str, Any]] = {}
    for row in records:
        account_id = row.get("account_id")
        target_account_id = row.get("target_account_id")
        if not isinstance(account_id, int) or not isinstance(target_account_id, int):
            continue
        pair_key = (account_id, target_account_id)
        if pair_key not in latest_record_map:
            latest_record_map[pair_key] = row

    rows: list[dict[str, Any]] = []
    for pair in pair_cards:
        left_id = int(pair["left_account_id"])
        right_id = int(pair["right_account_id"])

        left_to_right = latest_record_map.get((left_id, right_id))
        right_to_left = latest_record_map.get((right_id, left_id))

        left_status = left_to_right["status"] if left_to_right else "not_sent"
        right_status = right_to_left["status"] if right_to_left else "not_sent"

        left_success = left_status == "success"
        right_success = right_status == "success"
        has_failure = left_status == "failed" or right_status == "failed"

        if left_success and right_success:
            pair_progress = "mutual_success"
        elif left_success or right_success:
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
                "left_to_right_error": left_to_right.get("error_code")
                if left_to_right
                else None,
                "right_to_left_error": right_to_left.get("error_code")
                if right_to_left
                else None,
                "pair_progress": pair_progress,
            }
        )

    return rows


def build_daily_gift_context(
    session: Session,
    biz_date_local: str | None = None,
    q: str = "",
    sort_by: str = "updated_at",
    sort_order: str = "desc",
    page: int = 0,
    page_size: int = 10,
) -> dict[str, Any]:
    """构建每日送卡页面上下文。"""
    current_lang, t = get_current_i18n()
    selected_date = _normalize_biz_date_local(biz_date_local)
    current_biz_date_local = _today_local_date()

    records = list_daily_gift_records(session=session, biz_date_local=selected_date)
    pairs = list_active_gift_pairs(session=session)

    account_ids: set[int] = set()
    for row in records:
        account_ids.add(row.account_id)
        if isinstance(row.target_account_id, int):
            account_ids.add(row.target_account_id)
    for row in pairs:
        account_ids.add(row.account_id)
        if isinstance(row.target_account_id, int):
            account_ids.add(row.target_account_id)

    accounts = list_accounts_by_ids(session=session, account_ids=account_ids)
    account_name_map = {
        account.id: account.display_name
        for account in accounts
        if isinstance(account.id, int)
    }
    account_friend_id_map = {
        account.id: account.friend_id or "-"
        for account in accounts
        if isinstance(account.id, int)
    }

    record_rows_all: list[dict[str, Any]] = []
    success_count = 0
    failed_count = 0
    wait_count = 0

    for row in records:
        if row.status == "success":
            success_count += 1
        elif row.status == "failed":
            failed_count += 1
        else:
            wait_count += 1

        target_name = "-"
        if isinstance(row.target_account_id, int):
            target_name = account_name_map.get(row.target_account_id, "-")

        record_rows_all.append(
            {
                "id": row.id,
                "account_id": row.account_id,
                "account_name": account_name_map.get(
                    row.account_id, f"#{row.account_id}"
                ),
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

    pair_cards, pair_anomalies = _build_pair_views(
        pairs=pairs,
        account_name_map=account_name_map,
        account_friend_id_map=account_friend_id_map,
    )
    pair_send_status_rows = _build_pair_send_status_rows(
        records=record_rows_all,
        pair_cards=pair_cards,
    )

    q_text = q.strip().lower()
    filtered_records = []
    for row in record_rows_all:
        if not q_text:
            filtered_records.append(row)
            continue
        account_id_text = str(row.get("account_id") or "").lower()
        target_account_id_text = str(row.get("target_account_id") or "").lower()
        target_friend_id_text = str(row.get("target_friend_id") or "").lower()
        account_name_text = str(row.get("account_name") or "").lower()
        target_name_text = str(row.get("target_name") or "").lower()
        if (
            q_text in account_id_text
            or q_text in target_account_id_text
            or q_text in target_friend_id_text
            or q_text in account_name_text
            or q_text in target_name_text
        ):
            filtered_records.append(row)

    sort_direction_desc = sort_order != "asc"
    if sort_by == "account_id":
        filtered_records.sort(
            key=lambda item: int(item.get("account_id") or 0),
            reverse=sort_direction_desc,
        )
    elif sort_by == "status":
        filtered_records.sort(
            key=lambda item: str(item.get("status") or ""), reverse=sort_direction_desc
        )
    else:
        filtered_records.sort(
            key=lambda item: item.get("updated_at") or datetime.min,
            reverse=sort_direction_desc,
        )

    normalized_page = max(page, 0)
    normalized_page_size = min(max(page_size, 1), 100)
    records_total = len(filtered_records)
    start = normalized_page * normalized_page_size
    end = start + normalized_page_size
    paged_records = filtered_records[start:end]

    return {
        "records": paged_records,
        "records_total": records_total,
        "page": normalized_page,
        "page_size": normalized_page_size,
        "has_prev": normalized_page > 0,
        "has_next": end < records_total,
        "q": q,
        "sort_by": sort_by,
        "sort_order": sort_order,
        "pair_cards": pair_cards,
        "pair_send_status_rows": pair_send_status_rows,
        "pair_anomalies": pair_anomalies,
        "stats": {
            "total": len(record_rows_all),
            "success": success_count,
            "failed": failed_count,
            "waiting": wait_count,
        },
        "selected_biz_date_local": selected_date,
        "current_biz_date_local": current_biz_date_local,
        "recent_biz_dates": _build_recent_dates(selected_date),
        "t": t,
        "current_lang": current_lang,
    }
