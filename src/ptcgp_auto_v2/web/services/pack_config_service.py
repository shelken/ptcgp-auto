from ptcgp_auto_v2.db.engine import session_scope
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
    with session_scope() as session:
        repo = CardRepository(session)
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
    with session_scope() as session:
        repo = CardRepository(session)
        pack_names = repo.get_pack_names_by_set(set_code)
        if not pack_names:
            return []
        pack_label_map = repo.get_pack_labels_map(pack_names)
        return [
            _build_pack_option(name, pack_label_map.get(name)) for name in pack_names
        ]


def build_pack_config_context(account_id: int) -> dict:
    """构建补充包配置弹窗数据。"""
    card_sets = build_card_sets_options()
    with session_scope() as session:
        config_repo = AccountPackConfigRepository(session)
        config = config_repo.get_by_account_and_type(account_id, "daily")

        current_boosters = []
        target_set = (
            config.set_code if config else (card_sets[0]["code"] if card_sets else None)
        )
        pack_label_map: dict[str, str | None] = {}
        if target_set:
            card_repo = CardRepository(session)
            current_boosters = card_repo.get_pack_names_by_set(target_set)
            pack_label_map = card_repo.get_pack_labels_map(current_boosters)
    current_booster_options = []
    for name in current_boosters:
        current_booster_options.append(_build_pack_option(name, pack_label_map.get(name)))

    return {
        "account_id": account_id,
        "config": config.to_dict() if config else None,
        "selected_set_code": config.set_code if config else "",
        "selected_booster_name": config.booster_name if config else "",
        "card_sets": card_sets,
        "current_boosters": current_booster_options,
    }


def build_save_account_pack_config(
    account_id: int, set_code: str, booster_name: str
) -> None:
    """保存账号补充包配置。

    当 set_code 为空时，删除该账号的配置（清空设置）。
    """
    with session_scope() as session:
        repo = AccountPackConfigRepository(session)
        if not set_code:
            repo.delete_by_account_and_type(account_id, "daily")
            return
        config = AccountPackConfig.create_daily(account_id, set_code, booster_name)
        repo.upsert(config)
