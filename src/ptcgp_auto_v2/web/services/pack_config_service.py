from ptcgp_auto_v2.db.models.account_pack_config import AccountPackConfig
from ptcgp_auto_v2.db.repositories import CardRepository, AccountPackConfigRepository
from ptcgp_auto_v2.web.utils.i18n import resolve_label_json


def _build_pack_option(pack_name: str, label_data: str | None) -> dict:
    """构建子包选项（保留 value，展示本地化名称）。"""
    display_name = resolve_label_json(label_data, fallback=pack_name)
    return {
        "name": pack_name,
        "display_name": display_name,
    }


def build_card_sets_options() -> list[dict]:
    """构建全部卡包系列选项。"""
    repo = CardRepository()
    sets = repo.get_all_sets()
    return [
        {
            "code": item.code,
            "name": item.name,
            "display_name": resolve_label_json(item.label_data, fallback=item.name),
        }
        for item in sets
    ]


def build_set_boosters_options(set_code: str) -> list:
    """构建指定系列的补充包选项。"""
    repo = CardRepository()
    pack_names = repo.get_pack_names_by_set(set_code)
    if not pack_names:
        return []
    packs = [pack for pack in repo.get_all_packs() if pack.name in set(pack_names)]
    pack_map = {pack.name: pack for pack in packs}
    options = []
    for name in pack_names:
        pack = pack_map.get(name)
        options.append(_build_pack_option(name, pack.label_data if pack else None))
    return options


def build_pack_config_context(account_id: int) -> dict:
    """构建补充包配置弹窗数据。"""
    config_repo = AccountPackConfigRepository()
    card_repo = CardRepository()
    config = config_repo.get_by_account_and_type(account_id, "daily")
    card_sets = build_card_sets_options()

    current_boosters = []
    target_set = (
        config.pack_code if config else (card_sets[0]["code"] if card_sets else None)
    )
    if target_set:
        current_boosters = card_repo.get_pack_names_by_set(target_set)
    all_packs = card_repo.get_all_packs()
    pack_map = {pack.name: pack for pack in all_packs}
    current_booster_options = []
    for name in current_boosters:
        pack = pack_map.get(name)
        current_booster_options.append(
            _build_pack_option(name, pack.label_data if pack else None)
        )

    return {
        "account_id": account_id,
        "config": config,
        "card_sets": card_sets,
        "current_boosters": current_booster_options,
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
