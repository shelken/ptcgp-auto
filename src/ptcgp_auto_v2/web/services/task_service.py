from typing import Any

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


def list_task_status_view(
    session: Session,
    page: int,
    page_size: int,
    status: list[str],
    task_type: list[str],
    account_id: int | None,
    sort_by: str,
    sort_order: str,
) -> tuple[list[dict[str, Any]], bool]:
    """获取任务状态视图数据。"""
    instances, has_more = fetch_task_instances(
        session=session,
        page=page,
        page_size=page_size,
        status=status,
        task_type=task_type,
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
        next_run_at = instance.next_run_at or computed_next_run_at

        next_run_at_is_past = next_run_at is not None and next_run_at <= now

        rows.append(
            {
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
        )

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

            rows[-1]["target_pack_label"] = target_pack_label
            rows[-1]["target_pack_auto"] = target_pack_auto

    return rows, has_more


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
