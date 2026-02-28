from sqlmodel import Session

from ptcgp_auto_v2.db.models.account_pack_config import AccountPackConfig
from ptcgp_auto_v2.db.repositories import CardRepository, AccountPackConfigRepository


def build_card_sets_options() -> list[dict]:
    """构建全部卡包系列选项。"""
    repo = CardRepository()
    sets = repo.get_all_sets()
    return [{"code": item.code, "name": item.name} for item in sets]


def build_set_boosters_options(set_code: str) -> list:
    """构建指定系列的补充包选项。"""
    repo = CardRepository()
    return repo.get_pack_names_by_set(set_code)


def build_pack_config_context(account_id: int) -> dict:
    """构建补充包配置弹窗数据。"""
    config_repo = AccountPackConfigRepository()
    card_repo = CardRepository()
    config = config_repo.get_by_account_and_type(account_id, "daily")
    card_sets = card_repo.get_all_sets()

    current_boosters = []
    target_set = (
        config.pack_code if config else (card_sets[0].code if card_sets else None)
    )
    if target_set:
        current_boosters = card_repo.get_pack_names_by_set(target_set)

    return {
        "account_id": account_id,
        "config": config,
        "card_sets": card_sets,
        "current_boosters": current_boosters,
    }


def build_save_account_pack_config(
    account_id: int, pack_code: str, booster_name: str
) -> None:
    """保存账号补充包配置。

    当 pack_code 为空时，删除该账号的配置（清空设置）。
    """
    repo = AccountPackConfigRepository()
    if not pack_code:
        repo.delete_by_account_and_type(account_id, "daily")
        return
    config = AccountPackConfig(
        account_id=account_id,
        type="daily",
        pack_code=pack_code,
        booster_name=booster_name,
    )
    repo.upsert(config)
