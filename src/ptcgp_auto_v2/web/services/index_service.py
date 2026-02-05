from sqlmodel import Session, select, distinct

from ptcgp_auto_v2.db.models.card import Card
from ptcgp_auto_v2.db.repositories import CardRepository
from ptcgp_auto_v2.web.utils.element_utils import normalize_elements
from ptcgp_auto_v2.web.utils.form_utils import parse_json_label
from ptcgp_auto_v2.web.utils.i18n import get_translations, normalize_lang


def build_index_context(session: Session, lang: str) -> dict:
    """构建首页渲染所需上下文。"""
    current_lang = normalize_lang(lang)
    t = get_translations(current_lang)

    rarities = session.exec(select(distinct(Card.rarity)).order_by(Card.rarity)).all()
    rarities = [item for item in rarities if item]
    rarity_order = {
        "C": 1,
        "U": 2,
        "R": 3,
        "RR": 4,
        "AR": 5,
        "SR": 6,
        "SAR": 7,
        "UR": 8,
        "IM": 9,
        "S": 10,
        "SSR": 11,
    }
    rarities.sort(key=lambda item: rarity_order.get(item, 99))

    card_types = session.exec(select(distinct(Card.type)).order_by(Card.type)).all()
    card_types = [item for item in card_types if item]

    elements = session.exec(select(distinct(Card.element)).order_by(Card.element)).all()
    elements = normalize_elements(elements)

    card_repo = CardRepository()
    card_sets = card_repo.get_all_sets()
    packs = card_repo.get_all_packs()

    lang_key = "zh" if current_lang.startswith("zh") else "en"
    sets_data = [
        {"code": item.code, "label": parse_json_label(item.label_data)}
        for item in card_sets
    ]
    packs_data = [
        {
            "name": item.name,
            "set_code": item.set_code,
            "label": parse_json_label(item.label_data),
        }
        for item in packs
    ]

    return {
        "rarities": rarities,
        "card_types": card_types,
        "elements": elements,
        "card_sets": sets_data,
        "packs": packs_data,
        "lang_key": lang_key,
        "t": t,
        "current_lang": current_lang,
    }
