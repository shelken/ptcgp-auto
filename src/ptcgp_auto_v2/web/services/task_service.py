from datetime import datetime
from typing import Any
from urllib.parse import urlencode

from sqlmodel import Session, select

from ptcgp_auto_v2.core.task_plan_utils import (
    build_account_plan_cache,
    compute_next_run_for_instance,
)
from ptcgp_auto_v2.config.constants import PACK_AUTO_EXCLUDE_SET_CODES
from ptcgp_auto_v2.config.settings import get_settings
from ptcgp_auto_v2.db.models.account import Account
from ptcgp_auto_v2.db.models.account_pack_config import AccountPackConfig
from ptcgp_auto_v2.db.repositories import CardRepository, PackRecordRepository
from ptcgp_auto_v2.utils.pack_auto_selector import select_pack_for_account
from ptcgp_auto_v2.db.repositories import TaskInstanceRepository
from ptcgp_auto_v2.web.queries.task_queries import (
    fetch_task_instances,
    reset_completed_task_instances,
)
from ptcgp_auto_v2.web.utils.view_helpers import format_datetime_iso
from ptcgp_auto_v2.web.utils.filter_utils import (
    normalize_page,
    normalize_page_size,
)


def build_tasks_page_url(
    page: int,
    lang: str,
    status: list[str],
    task_type: list[str],
    account_id: int | None,
    sort_by: str,
    sort_order: str,
) -> str:
    """构建任务分页 URL。"""
    params = [("page", page), ("lang", lang)]
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
    """构建任务列表视图上下文（统一列表协议）。

    返回字段:
        - items: 任务列表
        - page: 当前页码
        - page_size: 每页大小
        - has_prev: 是否有上一页
        - has_next: 是否有下一页
        - total: 总数量（估算值，基于当前页数据）
    """
    normalized_page = normalize_page(page)
    normalized_page_size = normalize_page_size(page_size)

    instances, has_more = fetch_task_instances(
        session=session,
        page=normalized_page,
        page_size=normalized_page_size,
        status=status or [],
        task_type=task_type or [],
        account_id=account_id,
        sort_by=sort_by,
        sort_order=sort_order,
    )

    account_cache: dict[int, dict] = {}
    pack_configs_map: dict[int, AccountPackConfig] = {}
    auto_pack_map: dict[int, dict] = {}
    account_ids = [
        instance.account_id for instance in instances if instance.account_id is not None
    ]
    if account_ids:
        config_stm = select(AccountPackConfig).where(
            AccountPackConfig.type == "daily",
            AccountPackConfig.account_id.in_(account_ids),
        )
        configs = session.exec(config_stm).all()
        pack_configs_map = {item.account_id: item for item in configs}

        settings = get_settings()
        card_repo = CardRepository()
        record_repo = PackRecordRepository()
        for instance in instances:
            if instance.account_id is None:
                continue
            if instance.account_id in pack_configs_map:
                continue
            account = instance.account
            if not account:
                continue
            if instance.account_id in auto_pack_map:
                continue
            selected = select_pack_for_account(
                account=account,
                strategy=settings.pack_auto_strategy,
                card_repo=card_repo,
                record_repo=record_repo,
                exclude_set_codes=PACK_AUTO_EXCLUDE_SET_CODES,
            )
            if selected:
                auto_pack_map[instance.account_id] = selected
    rows: list[dict[str, Any]] = []
    now = datetime.now()
    for instance in instances:
        account = instance.account
        if not account or account.id is None:
            continue

        if account.id not in account_cache:
            account_cache[account.id] = build_account_plan_cache(account)

        cache = account_cache[account.id]
        computed_next_run_at, effective_reset_type, interval_seconds, plan_source = (
            compute_next_run_for_instance(instance, cache)
        )
        # 手动重置后 next_run_at 为 None，不再 fallback 到计算值，确保显示为空
        next_run_at = instance.next_run_at

        next_run_at_is_past = next_run_at is not None and next_run_at <= now

        row_data: dict[str, Any] = {
            "id": instance.id,
            "account_id": account.id,
            "account_name": account.nickname
            or account.display_name
            or str(account.id),
            "task_type": instance.task_type,
            "status": instance.status,
            "reset_type": effective_reset_type.value,
            "last_completed_at": instance.last_completed_at,
            "last_completed_at_iso": format_datetime_iso(
                instance.last_completed_at
            ),
            "updated_at": instance.updated_at,
            "error_message": instance.error_message,
            "next_run_at": next_run_at,
            "next_run_at_iso": format_datetime_iso(next_run_at),
            "next_run_at_is_past": next_run_at_is_past,
            "interval_seconds": interval_seconds,
            "plan_name": plan_source["name"] if plan_source else None,
            "plan_priority": plan_source["priority"] if plan_source else None,
            "target_pack_label": None,
            "target_pack_auto": False,
        }

        if instance.task_type == "open_pack":
            target_pack_label = None
            target_pack_auto = False
            config = pack_configs_map.get(account.id)
            if config:
                target_pack_label = f"{config.pack_code}/{config.booster_name}"
            else:
                auto_pack = auto_pack_map.get(account.id)
                if auto_pack:
                    target_pack_label = (
                        f"{auto_pack['pack_code']}/{auto_pack['booster_name']}"
                    )
                    target_pack_auto = True

            row_data["target_pack_label"] = target_pack_label
            row_data["target_pack_auto"] = target_pack_auto

        rows.append(row_data)

    # 估算总数：当前页数量 + (是否有下一页 ? 估算更多)
    # 由于 has_more 机制，我们知道是否有更多数据
    estimated_total = len(rows) + (normalized_page * normalized_page_size)
    if has_more:
        estimated_total += normalized_page_size  # 至少还有一页

    return {
        "items": rows,
        "page": normalized_page,
        "page_size": normalized_page_size,
        "has_prev": normalized_page > 0,
        "has_next": has_more,
        "total": estimated_total,
    }


def recompute_next_run_at_for_account(
    account: Account, task_types: list[str] | None
) -> None:
    """重算指定账号的任务 next_run_at。"""
    if account.id is None:
        return
    account_cache = build_account_plan_cache(account)
    if task_types is None:
        task_types = list(account_cache["config"].keys())
    if not task_types:
        return
    repo = TaskInstanceRepository()
    instances = repo.list_by_account_and_task_types(account.id, task_types)
    if not instances:
        return
    for instance in instances:
        next_run_at, _, _, _ = compute_next_run_for_instance(instance, account_cache)
        instance.next_run_at = next_run_at
    repo.update_next_run_at(instances)


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
