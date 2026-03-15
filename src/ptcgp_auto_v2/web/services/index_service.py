from sqlmodel import Session, select, distinct

from ptcgp_auto_v2.db.models.card import Card
from ptcgp_auto_v2.db.repositories import CardRepository, NotificationRepository
from ptcgp_auto_v2.web.utils.element_utils import normalize_elements
from ptcgp_auto_v2.web.utils.form_utils import parse_json_label
from ptcgp_auto_v2.web.utils.i18n import resolve_label
from ptcgp_auto_v2.config.rarity_icons import RARITY_META


def build_index_context(session: Session) -> dict:
    """构建首页渲染所需上下文。"""
    rarities = session.exec(select(distinct(Card.rarity)).order_by(Card.rarity)).all()
    rarities = [item for item in rarities if item]
    # 从 RARITY_META 动态构建排序权重（单一数据源）
    rarity_order = {code: meta["priority"] for code, meta in RARITY_META.items()}
    rarities.sort(key=lambda item: rarity_order.get(item, 99))

    card_types = session.exec(select(distinct(Card.type)).order_by(Card.type)).all()
    card_types = [item for item in card_types if item]

    elements = session.exec(select(distinct(Card.element)).order_by(Card.element)).all()
    elements = normalize_elements(elements)

    card_repo = CardRepository()
    card_sets = card_repo.get_all_sets()
    packs = card_repo.get_all_packs()

    # 获取未读通知数量（用于通知面板按钮状态）
    notification_repo = NotificationRepository()
    unread_count = notification_repo.count_unread()

    sets_data = []
    for item in card_sets:
        label_dict = parse_json_label(item.label_data)
        sets_data.append(
            {
                "code": item.code,
                "label": label_dict,
                "display_name": resolve_label(label_dict, fallback=item.code),
            }
        )

    packs_data = []
    for item in packs:
        label_dict = parse_json_label(item.label_data)
        packs_data.append(
            {
                "name": item.name,
                "set_code": item.set_code,
                "label": label_dict,
                "display_name": resolve_label(label_dict, fallback=item.name),
            }
        )

    return {
        "rarities": rarities,
        "card_types": card_types,
        "elements": elements,
        "card_sets": sets_data,
        "packs": packs_data,
        "unread_count": unread_count,
    }
