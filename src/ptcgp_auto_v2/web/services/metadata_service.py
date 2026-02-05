import json

from ptcgp_auto_v2.db.repositories import CardRepository
from ptcgp_auto_v2.web.queries.metadata_queries import build_label_dict
from ptcgp_auto_v2.web.utils.form_utils import parse_json_label
from ptcgp_auto_v2.web.utils.i18n import get_translations, normalize_lang


def build_metadata_context(lang: str) -> dict:
    """构建元数据管理视图数据。"""
    current_lang = normalize_lang(lang)
    t = get_translations(current_lang)
    repo = CardRepository()
    sets = repo.get_all_sets()
    packs = repo.get_all_packs()

    sets_data = []
    for item in sets:
        data = item.model_dump()
        data["label_dict"] = build_label_dict(item.label_data)
        sets_data.append(data)

    packs_data = []
    for item in packs:
        data = item.model_dump()
        data["label_dict"] = build_label_dict(item.label_data)
        packs_data.append(data)

    packs_by_set: dict[str, list[dict]] = {}
    for item in packs_data:
        set_code = item["set_code"]
        packs_by_set.setdefault(set_code, []).append(item)

    return {
        "sets": sets_data,
        "packs_by_set": packs_by_set,
        "t": t,
        "current_lang": current_lang,
    }


def update_set_label(code: str, label_zh: str) -> None:
    """更新卡包系列中文名。"""
    repo = CardRepository()
    card_set = repo.get_set_by_code(code)
    if not card_set:
        return
    labels = parse_json_label(card_set.label_data)
    labels["zh"] = label_zh
    repo.update_set_label(code, json.dumps(labels, ensure_ascii=False))


def update_pack_label(name: str, label_zh: str) -> None:
    """更新补充包中文名。"""
    repo = CardRepository()
    pack = repo.get_pack_by_name(name)
    if not pack:
        return
    labels = parse_json_label(pack.label_data)
    labels["zh"] = label_zh
    repo.update_pack_label(name, json.dumps(labels, ensure_ascii=False))
