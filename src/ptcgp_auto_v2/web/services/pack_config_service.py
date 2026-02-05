from sqlmodel import Session

from ptcgp_auto_v2.db.models.account_pack_config import AccountPackConfig
from ptcgp_auto_v2.db.repositories import CardRepository, AccountPackConfigRepository
from ptcgp_auto_v2.web.utils.i18n import get_translations, normalize_lang


def list_card_sets() -> list[dict]:
    """获取全部卡包系列列表。"""
    repo = CardRepository()
    sets = repo.get_all_sets()
    return [{"code": item.code, "name": item.name} for item in sets]


def list_set_boosters(set_code: str) -> list:
    """获取指定系列的补充包列表。"""
    repo = CardRepository()
    data = repo.get_packs_by_set(set_code)
    if not data or set_code not in data:
        return []
    return data[set_code]["boosters"]


def build_pack_config_context(account_id: int, lang: str) -> dict:
    """构建补充包配置弹窗数据。"""
    current_lang = normalize_lang(lang)
    t = get_translations(current_lang)

    config_repo = AccountPackConfigRepository()
    card_repo = CardRepository()
    config = config_repo.get_by_account_and_type(account_id, "daily")
    card_sets = card_repo.get_all_sets()

    current_boosters = []
    target_set = (
        config.pack_code if config else (card_sets[0].code if card_sets else None)
    )
    if target_set:
        data = card_repo.get_packs_by_set(target_set)
        if data and target_set in data:
            current_boosters = data[target_set]["boosters"]

    return {
        "account_id": account_id,
        "config": config,
        "card_sets": card_sets,
        "current_boosters": current_boosters,
        "t": t,
        "current_lang": current_lang,
    }


def save_account_pack_config(
    account_id: int, pack_code: str, booster_name: str
) -> None:
    """保存账号补充包配置。"""
    repo = AccountPackConfigRepository()
    config = AccountPackConfig(
        account_id=account_id,
        type="daily",
        pack_code=pack_code,
        booster_name=booster_name,
    )
    repo.upsert(config)
