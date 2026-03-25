from datetime import datetime
from typing import Any
from urllib.parse import urlencode

from sqlalchemy import String, cast as sa_cast
from sqlmodel import Session, col, or_, select

from ptcgp_auto_v2.config.constants import PACK_AUTO_EXCLUDE_SET_CODES
from ptcgp_auto_v2.config.settings import get_settings
from ptcgp_auto_v2.core.scheduling_service import (
    build_account_plan_cache,
    build_account_scheduling_context,
    build_task_scheduling_summary,
    resolve_account_dispatch_plan,
)
from ptcgp_auto_v2.db.models.account import Account
from ptcgp_auto_v2.db.models.account_pack_config import AccountPackConfig
from ptcgp_auto_v2.db.repositories import (
    CardRepository,
    PackRecordRepository,
    TaskInstanceRepository,
)
from ptcgp_auto_v2.utils.pack_auto_selector import select_pack_for_account
from ptcgp_auto_v2.web.queries.task_queries import (
    fetch_task_instances,
    reset_completed_task_instances,
)
from ptcgp_auto_v2.web.utils.filter_utils import (
    normalize_page,
    normalize_page_size,
)
from ptcgp_auto_v2.web.utils.i18n import get_current_lang
from ptcgp_auto_v2.web.utils.serialization import serialize_account
from ptcgp_auto_v2.web.utils.view_helpers import format_datetime_iso


def _resolve_open_pack_target(
    *,
    session: Session,
    account: Account,
    pack_configs_map: dict[int, AccountPackConfig],
) -> tuple[str | None, bool]:
    """返回开包任务目标包展示文案。"""
    if account.id is None:
        return None, False

    config = pack_configs_map.get(account.id)
    if config:
        return f"{config.set_code}/{config.booster_name}", False

    settings = get_settings()
    card_repo = CardRepository(session)
    record_repo = PackRecordRepository(session)
    auto_pack = select_pack_for_account(
        account=account,
        strategy=settings.pack_auto_strategy,
        card_repo=card_repo,
        record_repo=record_repo,
        exclude_set_codes=PACK_AUTO_EXCLUDE_SET_CODES,
    )
    if not auto_pack:
        return None, False
    return f"{auto_pack['set_code']}/{auto_pack['booster_name']}", True


def _build_tasks_page_url(
    *,
    page: int,
    page_size: int,
    status: list[str],
    task_type: list[str],
    account_id: int | None,
    sort_by: str,
    sort_order: str,
) -> str:
    """构建任务分页 URL。"""
    current_lang = get_current_lang()
    params: list[tuple[str, str | int]] = [
        ("page", page),
        ("page_size", page_size),
        ("lang", current_lang),
    ]
    for item in status:
        params.append(("status", item))
    for item in task_type:
        params.append(("task_type", item))
    if account_id is not None:
        params.append(("account_id", account_id))
    if sort_by:
        params.append(("sort_by", sort_by))
    if sort_order:
        params.append(("sort_order", sort_order))
    return f"/api/tasks?{urlencode(params)}"


def build_tasks_list_context(
    *,
    session: Session,
    page: int = 0,
    page_size: int = 10,
    status: list[str] | None = None,
    task_type: list[str] | None = None,
    account_id: int | None = None,
    sort_by: str = "",
    sort_order: str = "asc",
) -> dict[str, Any]:
    """构建任务列表视图上下文（统一列表协议）。"""
    normalized_page = normalize_page(page)
    normalized_page_size = normalize_page_size(page_size)

    normalized_status = status or []
    normalized_task_type = task_type or []
    instances, has_next, total = fetch_task_instances(
        session=session,
        page=normalized_page,
        page_size=normalized_page_size,
        status=normalized_status,
        task_type=normalized_task_type,
        account_id=account_id,
        sort_by=sort_by,
        sort_order=sort_order,
    )

    account_cache: dict[int, dict[str, Any]] = {}
    account_dispatch_plans: dict[int, Any | None] = {}
    pack_configs_map: dict[int, AccountPackConfig] = {}
    current_batch_tasks_map: dict[int, list[Any]] = {}
    account_ids = sorted(
        {instance.account_id for instance in instances if instance.account_id is not None}
    )
    if account_ids:
        config_stm = select(AccountPackConfig).where(
            AccountPackConfig.type == "daily",
            col(AccountPackConfig.account_id).in_(account_ids),
        )
        configs = session.exec(config_stm).all()
        pack_configs_map = {item.account_id: item for item in configs}
        current_batch_tasks_map = TaskInstanceRepository(session).get_pending_by_account_ids(
            account_ids
        )

    rows: list[dict[str, Any]] = []
    now = datetime.now()
    for instance in instances:
        account = instance.account
        if not account or account.id is None:
            continue

        if account.id not in account_cache:
            account_cache[account.id] = build_account_plan_cache(account)
            current_batch_tasks = current_batch_tasks_map.get(account.id, [])
            if current_batch_tasks:
                account_dispatch_plans[account.id] = resolve_account_dispatch_plan(
                    account,
                    current_batch_tasks,
                    build_account_scheduling_context(account),
                )
            else:
                account_dispatch_plans[account.id] = None

        summary = build_task_scheduling_summary(
            instance,
            account_cache[account.id],
            now,
            account_dispatch_plans[account.id],
        )
        next_run_at_is_past = (
            summary.next_run_at is not None and summary.next_run_at <= now
        )

        row_data: dict[str, Any] = {
            "id": instance.id,
            "account_id": account.id,
            "account_name": account.nickname or account.display_name or str(account.id),
            "task_type": instance.task_type,
            "status": instance.status,
            "reset_type": summary.effective_reset_type,
            "last_completed_at": instance.last_completed_at,
            "last_completed_at_iso": format_datetime_iso(instance.last_completed_at),
            "last_duration_seconds": instance.last_duration_seconds,
            "updated_at": instance.updated_at,
            "error_message": instance.error_message,
            "next_run_at": summary.next_run_at,
            "next_run_at_iso": format_datetime_iso(summary.next_run_at),
            "next_run_at_is_past": next_run_at_is_past,
            "interval_seconds": summary.interval_seconds,
            "plan_name": summary.plan_name,
            "plan_priority": summary.plan_priority,
            "dispatch_category": summary.dispatch_category,
            "dispatch_label_key": summary.dispatch_label_key,
            "dispatch_css_class": summary.dispatch_css_class,
            "dispatch_rank": summary.dispatch_rank,
            "dispatch_rank_total": summary.dispatch_rank_total,
            "target_pack_label": None,
            "target_pack_auto": False,
        }

        if instance.task_type != "open_pack":
            rows.append(row_data)
            continue

        target_pack_label, target_pack_auto = _resolve_open_pack_target(
            session=session,
            account=account,
            pack_configs_map=pack_configs_map,
        )
        row_data["target_pack_label"] = target_pack_label
        row_data["target_pack_auto"] = target_pack_auto

        rows.append(row_data)

    return {
        "items": rows,
        "page": normalized_page,
        "page_size": normalized_page_size,
        "has_prev": normalized_page > 0,
        "has_next": has_next,
        "total": total,
        "next_page_url": _build_tasks_page_url(
            page=normalized_page + 1,
            page_size=normalized_page_size,
            status=normalized_status,
            task_type=normalized_task_type,
            account_id=account_id,
            sort_by=sort_by,
            sort_order=sort_order,
        ),
        "prev_page_url": _build_tasks_page_url(
            page=max(normalized_page - 1, 0),
            page_size=normalized_page_size,
            status=normalized_status,
            task_type=normalized_task_type,
            account_id=account_id,
            sort_by=sort_by,
            sort_order=sort_order,
        ),
    }


def list_task_filter_accounts(
    *,
    session: Session,
    q: str = "",
    limit: int = 20,
) -> list[dict[str, Any]]:
    """获取任务筛选账号候选（轻量查询）。"""
    normalized_q = (q or "").strip()
    normalized_limit = min(max(limit, 1), 50)

    statement = select(Account).order_by(col(Account.id)).limit(normalized_limit)
    if normalized_q:
        like_value = f"%{normalized_q}%"
        filters: list[Any] = [
            sa_cast(Account.nickname, String).ilike(like_value),
            sa_cast(Account.friend_id, String).ilike(like_value),
            sa_cast(Account.game_id, String).ilike(like_value),
        ]
        if normalized_q.isdigit():
            filters.append(col(Account.id) == int(normalized_q))
        statement = statement.where(or_(*filters))

    accounts = session.exec(statement).all()
    return [serialize_account(account) for account in accounts]


def build_task_list_render_context(
    *,
    session: Session,
    page: int,
    page_size: int,
    status: list[str],
    task_type: list[str],
    account_id: int | None,
    account_q: str,
    sort_by: str,
    sort_order: str,
    table_only: bool,
) -> dict[str, Any]:
    """构建任务列表模板渲染上下文。"""
    from ptcgp_auto_v2.core.task_base import TaskRegistry
    from ptcgp_auto_v2.core.task_status import TaskStatus

    context = build_tasks_list_context(
        session=session,
        page=page,
        page_size=page_size,
        status=status,
        task_type=task_type,
        account_id=account_id,
        sort_by=sort_by,
        sort_order=sort_order,
    )

    context["status_options"] = [status_item.value for status_item in TaskStatus]
    context["task_types"] = TaskRegistry.all_types()
    context["accounts"] = list_task_filter_accounts(
        session=session, q=account_q, limit=20
    )
    context["selected_status"] = status
    context["selected_task_type"] = task_type
    context["selected_account_id"] = account_id
    context["selected_account_query"] = account_q
    context["selected_sort_by"] = sort_by
    context["selected_sort_order"] = sort_order
    context["table_only"] = table_only
    return context


def reset_completed_tasks_by_filters(
    session: Session,
    status: list[str],
    task_type: list[str],
    account_id: int | None,
) -> int:
    """按筛选条件重置已完成任务为待执行。"""
    return reset_completed_task_instances(
        session=session,
        status=status,
        task_type=task_type,
        account_id=account_id,
    )
