from typing import Any

from sqlalchemy.orm import selectinload
from sqlmodel import Session, select
from typing import cast

from ptcgp_auto_v2.config.constants import PACK_AUTO_EXCLUDE_SET_CODES
from ptcgp_auto_v2.config.settings import get_settings
from ptcgp_auto_v2.core.scheduling_service import recompute_and_sync_account_scheduling
from ptcgp_auto_v2.db.engine import session_scope
from ptcgp_auto_v2.db.models.account import Account
from ptcgp_auto_v2.db.models.account_pack_config import AccountPackConfig
from ptcgp_auto_v2.db.models.account_task_plan import AccountTaskPlan
from ptcgp_auto_v2.db.repositories import (
    AccountRepository,
    CardRepository,
    PackRecordRepository,
    TaskPlanRepository,
)
from ptcgp_auto_v2.utils.pack_auto_selector import select_pack_for_account
from ptcgp_auto_v2.web.services._list_query_state import build_sorted_list_query_state
from ptcgp_auto_v2.web.utils.serialization import serialize_account, serialize_task_plan


def _match_account(item: Account, query: str) -> bool:
    """判断账号是否匹配搜索词。"""
    account_id_text = str(item.id or "")
    nickname_text = (item.nickname or "").lower()
    display_name_text = (item.display_name or "").lower()
    friend_id_text = (item.friend_id or "").lower()
    game_id_text = (item.game_id or "").lower()
    return (
        query in account_id_text
        or query in nickname_text
        or query in display_name_text
        or query in friend_id_text
        or query in game_id_text
    )


def _serialize_account_task_plan_assoc(assoc: AccountTaskPlan) -> dict[str, Any]:
    """把账号计划关联转成纯数据。"""
    return {
        **assoc.model_dump(),
        "task_plan": (
            serialize_task_plan(assoc.task_plan) if assoc.task_plan else None
        ),
    }


def _serialize_account(
    account: Account,
    *,
    include_assocs: bool = False,
) -> dict[str, Any]:
    """把账号转成纯数据。"""
    data = serialize_account(account)
    if include_assocs:
        data["task_plan_associations"] = [
            _serialize_account_task_plan_assoc(assoc)
            for assoc in account.task_plan_associations or []
        ]
    return data


def _resolve_auto_pack_map(
    *,
    session: Session,
    accounts: list[Account],
    pack_configs_map: dict[int, dict[str, Any]],
) -> dict[int, dict[str, Any]]:
    """为未配置固定包的账号补齐自动选包结果。"""
    settings = get_settings()
    card_repo = CardRepository(session)
    record_repo = PackRecordRepository(session)
    auto_pack_map: dict[int, dict[str, Any]] = {}
    for account in accounts:
        if account.id is None or account.id in pack_configs_map:
            continue
        auto_pack = select_pack_for_account(
            account=account,
            strategy=settings.pack_auto_strategy,
            card_repo=card_repo,
            record_repo=record_repo,
            exclude_set_codes=PACK_AUTO_EXCLUDE_SET_CODES,
        )
        if auto_pack:
            auto_pack_map[account.id] = auto_pack
    return auto_pack_map


def build_accounts_list_context(
    *,
    session: Session,
    q: str = "",
    sort_by: str = "id",
    sort_order: str = "asc",
    page: int = 0,
    page_size: int = 10,
) -> dict:
    """构建账号管理列表视图上下文（统一列表协议：q/sort/page）。"""
    repo = AccountRepository(session)
    accounts = repo.get_all()

    list_state = build_sorted_list_query_state(
        q=q,
        sort_by=sort_by,
        sort_order=sort_order,
        page=page,
        page_size=page_size,
        allowed_sort_fields={"id", "nickname", "friend_id"},
        default_sort_by="id",
    )

    if list_state.normalized_q:
        accounts = [item for item in accounts if _match_account(item, list_state.normalized_q)]

    def _sort_value(item: Account):
        if list_state.sort_by == "nickname":
            return (item.nickname or item.display_name or "").lower()
        if list_state.sort_by == "friend_id":
            return (item.friend_id or "").lower()
        return item.id or 0

    accounts = sorted(
        accounts,
        key=_sort_value,
        reverse=(list_state.sort_order == "desc"),
    )

    total = len(accounts)
    start, end = list_state.page_bounds()
    page_accounts = accounts[start:end]
    accounts_page = [
        _serialize_account(item, include_assocs=True) for item in page_accounts
    ]

    config_stm = select(AccountPackConfig).where(AccountPackConfig.type == "daily")
    all_configs = session.exec(config_stm).all()
    pack_configs_map = {item.account_id: item.to_dict() for item in all_configs}

    return {
        "items": accounts_page,
        "pack_configs": pack_configs_map,
        "q": q,
        "sort_by": list_state.sort_by,
        "sort_order": list_state.sort_order,
        **list_state.page_meta(total=total),
    }


def build_account_edit_context(account_id: int) -> dict | None:
    """构建账号编辑弹窗数据。"""
    with session_scope() as session:
        repo = AccountRepository(session)
        account = repo.get_by_id(account_id)
        if not account:
            return None
        return {"account": _serialize_account(account)}


def build_accounts_packs_context(
    *, session: Session, pack_configs_map: dict[int, dict[str, Any]], account_ids: list[int] | None = None,
) -> dict[int, dict[str, Any]]:
    """构建自动选包映射，指定 account_ids 时只计算这些账号。"""
    repo = AccountRepository(session)
    if account_ids:
        accounts_map = repo.get_by_ids(account_ids)
        accounts = list(accounts_map.values())
    else:
        accounts = repo.get_all()
    return _resolve_auto_pack_map(
        session=session,
        accounts=accounts,
        pack_configs_map=pack_configs_map,
    )


def update_account_details(account_id: int, nickname: str, remark: str) -> None:
    """更新账号信息。"""
    with session_scope() as session:
        repo = AccountRepository(session)
        account = repo.get_by_id(account_id)
        if not account:
            return
        account.nickname = nickname
        account.remark = remark
        repo.update(account)


def build_account_plans_context(session: Session, account_id: int) -> dict | None:
    """构建账号计划编辑弹窗数据。"""
    statement = (
        select(Account)
        .where(Account.id == account_id)
        .options(
            selectinload(cast(Any, Account.task_plan_associations)).selectinload(
                cast(Any, AccountTaskPlan.task_plan)
            )
        )
    )
    account = session.exec(statement).first()
    if not account:
        return None

    plan_repo = TaskPlanRepository(session)
    current_assocs = [
        _serialize_account_task_plan_assoc(item)
        for item in sorted(account.task_plan_associations, key=lambda item: -item.priority)
    ]
    available_plans = [
        serialize_task_plan(item)
        for item in plan_repo.list_unassigned_for_account(account_id)
    ]

    return {
        "account": _serialize_account(account, include_assocs=True),
        "current_assocs": current_assocs,
        "available_plans": available_plans,
    }


def update_account_plans(account_id: int, data: list[dict]) -> None:
    """保存账号计划关联关系。"""
    with session_scope() as session:
        repo = AccountRepository(session)
        plans_data = []
        base_priority = 100
        for index, item in enumerate(data):
            plan_id = item.get("plan_id")
            is_active = item.get("is_active", True)
            if plan_id:
                priority = max(0, base_priority - (index * 10))
                plans_data.append(
                    {
                        "plan_id": int(plan_id),
                        "is_active": is_active,
                        "priority": priority,
                    }
                )
        repo.update_plan_associations(account_id, plans_data)

        account = repo.get_by_id(account_id)
        if not account:
            return
        recompute_and_sync_account_scheduling(
            session=session,
            account=account,
        )
