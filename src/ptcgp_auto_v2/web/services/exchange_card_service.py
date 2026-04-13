# -*- coding: utf-8 -*-
"""交换卡牌管理服务。"""

from datetime import datetime
from typing import Any, Optional

from sqlmodel import Session, select

from ptcgp_auto_v2.db.engine import session_scope
from ptcgp_auto_v2.db.models import Account, ExchangeCardRequest
from ptcgp_auto_v2.db.repositories.factory import RepositoryFactory
from ptcgp_auto_v2.services import ExchangeCardService as CoreExchangeCardService
from ptcgp_auto_v2.web.queries._query_helpers import normalize_pagination
from ptcgp_auto_v2.web.queries.exchange_card_queries import (
    list_exchange_requests,
    normalize_exchange_request_sort,
)
from ptcgp_auto_v2.web.utils.serialization import serialize_account


def create_exchange_request_with_task(
    from_account_id: int,
    to_account_id: int | None,
    to_friend_id: str,
    target_card_id: int,
    target_card_rarity: str,
) -> bool:
    """创建交换请求并确保任务实例为待执行状态。

    Returns:
        是否成功创建请求
    """
    created = CoreExchangeCardService.create_request(
        from_account_id=from_account_id,
        to_account_id=to_account_id,
        to_friend_id=to_friend_id,
        target_card_id=target_card_id,
        target_card_rarity=target_card_rarity,
    )
    if created is not None:
        with session_scope() as session:
            RepositoryFactory(session).task_instances().ensure_pending(
                account_id=from_account_id,
                task_type="exchange_cards",
                reset_type="once",
            )
        return True
    return False


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
    normalized_sort_by, normalized_sort_order = normalize_exchange_request_sort(
        sort_by, sort_order
    )
    normalized_page, normalized_page_size = normalize_pagination(
        page=page,
        page_size=page_size,
        max_size=100,
    )
    result = list_exchange_requests(
        session=session,
        account_id=account_id,
        status=status,
        q=q,
        sort_by=normalized_sort_by,
        sort_order=normalized_sort_order,
        page=normalized_page,
        page_size=normalized_page_size,
    )
    if isinstance(result, tuple):
        requests, total_items = result
    else:
        requests = result
        total_items = len(requests)
    accounts = [
        serialize_account(account) for account in session.exec(select(Account)).all()
    ]
    account_name_map = {
        account["id"]: (
            account["nickname"] or account["game_id"] or f"#{account['id']}"
        )
        for account in accounts
        if account["id"] is not None
    }

    rows: list[dict[str, Any]] = []
    for row in requests:
        data = row.model_dump()
        data["can_cancel"] = row.status in {"sending", "sended"}
        rows.append(data)
    status_options = sorted(
        {
            str(item)
            for item in session.exec(select(ExchangeCardRequest.status).distinct()).all()
            if item
        }
    )

    return {
        "requests": rows,
        "total_items": total_items,
        "page": normalized_page,
        "page_size": normalized_page_size,
        "has_prev": normalized_page > 0,
        "has_next": (normalized_page + 1) * normalized_page_size < total_items,
        "q": q,
        "sort_by": normalized_sort_by,
        "sort_order": normalized_sort_order,
        "accounts": accounts,
        "account_name_map": account_name_map,
        "status_options": status_options,
        "selected_account_id": account_id,
        "selected_status": status or "",
    }


def cancel_exchange_request(request_id: int, reason: str = "web_cancel") -> bool:
    """取消交换请求（仅 sending/sended）。"""
    with session_scope() as session:
        repos = RepositoryFactory(session)
        repo = repos.exchange_card_requests()
        request = repo.get_by_id(request_id)
        if request is None:
            return False
        if request.status not in {"sending", "sended"}:
            return False
        if request.status == "sending":
            repo.mark_canceled(request_id, reason=reason)
            return True

        repo.update_fields_by_id(
            request_id,
            cancel_reason=reason,
            next_check_at=datetime.now(),
        )
        repos.task_instances().ensure_pending(
            account_id=request.from_account_id,
            task_type="exchange_cards",
            reset_type="once",
        )
    return True
