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
from ptcgp_auto_v2.web.utils.i18n import get_translations, normalize_lang


def get_accounts_context(session: Session, lang: str) -> dict:
    """获取账号管理列表视图数据。"""
    current_lang = normalize_lang(lang)
    t = get_translations(current_lang)
    repo = AccountRepository()
    accounts = repo.get_all()

    config_stm = select(AccountPackConfig).where(AccountPackConfig.type == "daily")
    all_configs = session.exec(config_stm).all()
    pack_configs_map = {item.account_id: item for item in all_configs}

    auto_pack_map: dict[int, dict] = {}
    if accounts:
        settings = get_settings()
        card_repo = CardRepository()
        record_repo = PackRecordRepository()
        for account in accounts:
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
        "accounts": accounts,
        "pack_configs": pack_configs_map,
        "auto_pack_map": auto_pack_map,
        "t": t,
        "current_lang": current_lang,
    }


def build_account_edit_context(account_id: int, lang: str) -> dict | None:
    """构建账号编辑弹窗数据。"""
    current_lang = normalize_lang(lang)
    t = get_translations(current_lang)
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
    session: Session, account_id: int, lang: str
) -> dict | None:
    """构建账号计划编辑弹窗数据。"""
    current_lang = normalize_lang(lang)
    t = get_translations(current_lang)
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
