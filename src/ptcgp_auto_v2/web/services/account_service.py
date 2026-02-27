from sqlmodel import Session, select
from typing import Any, cast

from sqlalchemy.orm import selectinload

from ptcgp_auto_v2.db.models.account import Account
from ptcgp_auto_v2.db.models.account_task_plan import AccountTaskPlan
from ptcgp_auto_v2.config.constants import PACK_AUTO_EXCLUDE_SET_CODES
from ptcgp_auto_v2.config.settings import get_settings
from ptcgp_auto_v2.db.models.account_pack_config import AccountPackConfig
from ptcgp_auto_v2.db.repositories import (
    AccountRepository,
    CardRepository,
    PackRecordRepository,
    TaskPlanRepository,
)
from ptcgp_auto_v2.utils.pack_auto_selector import select_pack_for_account
from ptcgp_auto_v2.web.services.task_service import recompute_next_run_at_for_account
from ptcgp_auto_v2.web.utils.i18n import get_current_i18n


def _normalize_query_text(q: str | object | None) -> str:
    """归一化搜索词，兜底非字符串输入。"""
    if isinstance(q, str):
        return q.strip().lower()
    return ""


def get_accounts_context(
    session: Session,
    q: str = "",
    sort_by: str = "id",
    sort_order: str = "asc",
    page: int = 0,
    page_size: int = 10,
) -> dict:
    """获取账号管理列表视图数据（统一列表协议：q/sort/page）。"""
    current_lang, t = get_current_i18n()
    repo = AccountRepository()
    accounts = repo.get_all()

    normalized_q = _normalize_query_text(q)
    allowed_sort_fields = {"id", "nickname", "friend_id"}
    normalized_sort_by = sort_by if sort_by in allowed_sort_fields else "id"
    normalized_sort_order = "desc" if str(sort_order).lower() == "desc" else "asc"
    normalized_page = max(page, 0)
    normalized_page_size = min(max(page_size, 1), 100)

    if normalized_q:

        def _match_account(item: Account) -> bool:
            account_id_text = str(item.id or "")
            nickname_text = (item.nickname or "").lower()
            display_name_text = (item.display_name or "").lower()
            friend_id_text = (item.friend_id or "").lower()
            game_id_text = (item.game_id or "").lower()
            return (
                normalized_q in account_id_text
                or normalized_q in nickname_text
                or normalized_q in display_name_text
                or normalized_q in friend_id_text
                or normalized_q in game_id_text
            )

        accounts = [item for item in accounts if _match_account(item)]

    def _sort_value(item: Account):
        if normalized_sort_by == "nickname":
            return (item.nickname or item.display_name or "").lower()
        if normalized_sort_by == "friend_id":
            return (item.friend_id or "").lower()
        return item.id or 0

    accounts = sorted(
        accounts,
        key=_sort_value,
        reverse=(normalized_sort_order == "desc"),
    )

    total_items = len(accounts)
    start = normalized_page * normalized_page_size
    end = start + normalized_page_size
    accounts_page = accounts[start:end]
    has_prev = normalized_page > 0
    has_next = end < total_items

    config_stm = select(AccountPackConfig).where(AccountPackConfig.type == "daily")
    all_configs = session.exec(config_stm).all()
    pack_configs_map = {item.account_id: item for item in all_configs}

    auto_pack_map: dict[int, dict] = {}
    if accounts_page:
        settings = get_settings()
        card_repo = CardRepository()
        record_repo = PackRecordRepository()
        for account in accounts_page:
            if account.id is None or account.id in pack_configs_map:
                continue
            selected = select_pack_for_account(
                account=account,
                strategy=settings.pack_auto_strategy,
                card_repo=card_repo,
                record_repo=record_repo,
                exclude_set_codes=PACK_AUTO_EXCLUDE_SET_CODES,
            )
            if selected:
                auto_pack_map[account.id] = selected

    return {
        "accounts": accounts_page,
        "pack_configs": pack_configs_map,
        "auto_pack_map": auto_pack_map,
        "q": q,
        "sort_by": normalized_sort_by,
        "sort_order": normalized_sort_order,
        "page": normalized_page,
        "page_size": normalized_page_size,
        "has_prev": has_prev,
        "has_next": has_next,
        "total_items": total_items,
        "t": t,
        "current_lang": current_lang,
    }


def build_account_edit_context(account_id: int) -> dict | None:
    """构建账号编辑弹窗数据。"""
    current_lang, t = get_current_i18n()
    repo = AccountRepository()
    account = repo.get_by_id(account_id)
    if not account:
        return None
    return {"account": account, "t": t, "current_lang": current_lang}


def update_account_details(account_id: int, nickname: str, remark: str) -> None:
    """更新账号信息。"""
    repo = AccountRepository()
    account = repo.get_by_id(account_id)
    if not account:
        return
    account.nickname = nickname
    account.remark = remark
    repo.update(account)


def build_account_plans_context(
    session: Session, account_id: int
) -> dict | None:
    """构建账号计划编辑弹窗数据。"""
    current_lang, t = get_current_i18n()
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

    plan_repo = TaskPlanRepository()
    all_plans = plan_repo.get_all()
    current_assocs = sorted(
        account.task_plan_associations, key=lambda item: -item.priority
    )
    associated_plan_ids = {assoc.task_plan_id for assoc in current_assocs}
    available_plans = [plan for plan in all_plans if plan.id not in associated_plan_ids]

    return {
        "account": account,
        "current_assocs": current_assocs,
        "available_plans": available_plans,
        "t": t,
        "current_lang": current_lang,
    }


def update_account_plans(account_id: int, data: list[dict]) -> None:
    """保存账号计划关联关系。"""
    repo = AccountRepository()
    plans_data = []
    base_priority = 100
    for index, item in enumerate(data):
        plan_id = item.get("plan_id")
        is_active = item.get("is_active", True)
        if plan_id:
            priority = max(0, base_priority - (index * 10))
            plans_data.append(
                {"plan_id": int(plan_id), "is_active": is_active, "priority": priority}
            )
    repo.update_plan_associations(account_id, plans_data)

    account = repo.get_by_id(account_id)
    if not account:
        return
    task_types: set[str] = set()
    for assoc in account.task_plan_associations or []:
        if not assoc.is_active or not assoc.task_plan:
            continue
        task_types.update(assoc.task_plan.task_types_list)
    recompute_next_run_at_for_account(account, list(task_types))
