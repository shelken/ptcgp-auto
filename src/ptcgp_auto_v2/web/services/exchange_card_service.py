# -*- coding: utf-8 -*-
"""交换卡牌管理服务。"""

from datetime import datetime
from typing import Any, Optional

from sqlmodel import Session, select

from ptcgp_auto_v2.db.models import Account
from ptcgp_auto_v2.db.repositories import (
    ExchangeCardRequestRepository,
    TaskInstanceRepository,
)
from ptcgp_auto_v2.web.queries.exchange_card_queries import list_exchange_requests
from ptcgp_auto_v2.web.utils.i18n import get_current_i18n


def build_exchange_card_context(
    session: Session,
    account_id: Optional[int] = None,
    status: Optional[str] = None,
    q: str = "",
    sort_by: str = "created_at",
    sort_order: str = "desc",
    page: int = 0,
    page_size: int = 10,
) -> dict[str, Any]:
    """构建交换记录管理视图数据。"""
    current_lang, t = get_current_i18n()
    result = list_exchange_requests(
        session=session,
        account_id=account_id,
        status=status,
        q=q,
        sort_by=sort_by,
        sort_order=sort_order,
        page=page,
        page_size=page_size,
    )
    if isinstance(result, tuple):
        requests, total_items = result
    else:
        requests = result
        total_items = len(requests)
    accounts = session.exec(select(Account)).all()
    account_name_map = {
        account.id: (account.nickname or account.game_id or f"#{account.id}")
        for account in accounts
    }

    rows: list[dict[str, Any]] = []
    for row in requests:
        can_cancel = row.status in {"sending", "sended"}
        rows.append(
            {
                "id": row.id,
                "from_account_id": row.from_account_id,
                "to_account_id": row.to_account_id,
                "to_friend_id": row.to_friend_id,
                "target_card_id": row.target_card_id,
                "target_card_rarity": row.target_card_rarity,
                "status": row.status,
                "failed_reason": row.failed_reason,
                "cancel_reason": row.cancel_reason,
                "created_at": row.created_at,
                "updated_at": row.updated_at,
                "can_cancel": can_cancel,
            }
        )

    return {
        "t": t,
        "current_lang": current_lang,
        "requests": rows,
        "total_items": total_items,
        "page": page,
        "page_size": page_size,
        "has_prev": page > 0,
        "has_next": (page + 1) * page_size < total_items,
        "q": q,
        "sort_by": sort_by,
        "sort_order": sort_order,
        "accounts": accounts,
        "account_name_map": account_name_map,
        "selected_account_id": account_id,
        "selected_status": status or "",
    }


def cancel_exchange_request(request_id: int, reason: str = "web_cancel") -> bool:
    """取消交换请求（仅 sending/sended）。"""
    repo = ExchangeCardRequestRepository()
    request = repo.get_by_id(request_id)
    if request is None:
        return False
    if request.status not in {"sending", "sended"}:
        return False
    if request.status == "sending":
        repo.mark_canceled(request, reason=reason)
        return True

    request.cancel_reason = reason
    request.next_check_at = datetime.now()
    request.updated_at = datetime.now()
    repo.update(request)

    TaskInstanceRepository().ensure_pending(
        account_id=request.from_account_id,
        task_type="exchange_cards",
        reset_type="once",
    )
    return True
