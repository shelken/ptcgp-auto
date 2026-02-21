# -*- coding: utf-8 -*-
"""通知管理页面服务。"""

import json
from typing import Any, Optional

from sqlmodel import Session, col, select

from ptcgp_auto_v2.config.constants import (
    HIGH_RARITY_TARGETS,
)
from ptcgp_auto_v2.config.notification import (
    NOTIFICATION_SCENE_LABEL_KEYS,
    NOTIFICATION_SCENE_OPTIONS,
    NOTIFICATION_TASK_STATUS_OPTIONS,
)
from ptcgp_auto_v2.db.models import Account, Card, NotificationConfig, Pack
from ptcgp_auto_v2.db.repositories import (
    NotificationConfigRepository,
    NotificationRepository,
)
from ptcgp_auto_v2.tasks import TaskRegistry
from ptcgp_auto_v2.web.queries.notification_queries import (
    list_notification_selectable_cards,
    list_notifications,
    list_recent_notifications,
    normalize_card_picker_sort,
    normalize_notification_sort,
)
from ptcgp_auto_v2.web.utils.i18n import get_translations, normalize_lang


SCENE_OPTIONS = list(NOTIFICATION_SCENE_OPTIONS)
TASK_STATUS_OPTIONS = list(NOTIFICATION_TASK_STATUS_OPTIONS)
RARITY_ORDER = {code: index for index, code in enumerate(HIGH_RARITY_TARGETS, start=1)}


def _build_scene_options(t: dict[str, Any]) -> list[dict[str, str]]:
    """构建场景下拉选项。"""
    fallback_labels = {
        "rare_card_obtained": "稀有卡牌",
        "task_status": "任务状态",
        "system_warning": "系统警告",
    }
    return [
        {
            "value": scene,
            "label": t.get(NOTIFICATION_SCENE_LABEL_KEYS[scene])
            or fallback_labels.get(scene, scene),
        }
        for scene in SCENE_OPTIONS
    ]


def _safe_json_loads(value: str | None) -> dict[str, Any]:
    """安全解析 JSON 字符串。"""
    if not value:
        return {}
    try:
        data = json.loads(value)
    except json.JSONDecodeError:
        return {}
    return data if isinstance(data, dict) else {}


def get_task_type_options() -> list[str]:
    """从任务注册表动态读取任务类型列表。"""
    return TaskRegistry.all_types()


def build_config_view(config: NotificationConfig) -> dict[str, Any]:
    """将通知配置模型转换为模板可用结构。"""
    return {
        "scene": config.scene,
        "enabled": config.enabled,
        "enabled_webhook": config.enabled_webhook,
        "extra_config": _safe_json_loads(config.extra_config),
    }


def normalize_scene(scene: str | None) -> str:
    """标准化通知场景参数。"""
    if scene in SCENE_OPTIONS:
        return scene
    return ""


def list_rarity_codes(session: Session) -> list[str]:
    """获取并排序数据库中的稀有度代码。"""
    rows = session.exec(select(Card.rarity).distinct()).all()
    rarities = [item for item in rows if item in HIGH_RARITY_TARGETS]
    if not rarities:
        return list(HIGH_RARITY_TARGETS)
    rarities.sort(key=lambda item: RARITY_ORDER.get(item, 99))
    return rarities


def list_cards_by_ids(session: Session, card_ids: list[int]) -> list[Card]:
    """按给定顺序查询卡牌。"""
    if not card_ids:
        return []
    card_map = {
        card.id: card
        for card in session.exec(select(Card).where(col(Card.id).in_(card_ids))).all()
        if card.id is not None
    }
    return [card_map[card_id] for card_id in card_ids if card_id in card_map]


def build_notification_card_selector_context(
    session: Session,
    lang: str,
    scene: str,
    selected_card_ids: list[int],
    q: str = "",
    rarity: str = "",
    set_code: str = "",
    pack_name: str = "",
    sort_by: str = "id",
    sort_order: str = "asc",
    page: int = 0,
    page_size: int = 24,
) -> dict[str, Any]:
    """构建通知配置卡牌选择器上下文。"""
    current_lang = normalize_lang(lang)
    t = get_translations(current_lang)
    normalized_page = max(page, 0)
    normalized_page_size = min(max(page_size, 1), 60)
    normalized_sort_by, normalized_sort_order = normalize_card_picker_sort(
        sort_by, sort_order
    )

    cards, total = list_notification_selectable_cards(
        session=session,
        q=q,
        rarity=rarity,
        set_code=set_code,
        pack_name=pack_name,
        sort_by=normalized_sort_by,
        sort_order=normalized_sort_order,
        page=normalized_page,
        page_size=normalized_page_size,
    )
    set_codes = list(session.exec(select(Card.set_code).distinct()).all())
    set_codes = sorted([item for item in set_codes if item])
    pack_names = list(session.exec(select(Pack.name).order_by(Pack.name)).all())
    pack_names = [item for item in pack_names if item]
    selected_card_rows = list_cards_by_ids(session, selected_card_ids)

    return {
        "t": t,
        "current_lang": current_lang,
        "scene": scene,
        "cards": cards,
        "selected_card_ids": selected_card_ids,
        "selected_cards": selected_card_rows,
        "card_selector_q": q,
        "card_selector_rarity": rarity,
        "card_selector_set_code": set_code,
        "card_selector_pack_name": pack_name,
        "card_selector_sort_by": normalized_sort_by,
        "card_selector_sort_order": normalized_sort_order,
        "card_selector_page": normalized_page,
        "card_selector_page_size": normalized_page_size,
        "card_selector_total": total,
        "card_selector_has_prev": normalized_page > 0,
        "card_selector_has_next": (normalized_page + 1) * normalized_page_size < total,
        "rarity_codes": list_rarity_codes(session),
        "set_codes": set_codes,
        "pack_names": pack_names,
    }


def build_notifications_context(
    session: Session,
    lang: str,
    scene: Optional[str] = None,
    account_id: Optional[int] = None,
    is_read: Optional[bool] = None,
    q: str = "",
    sort_by: str = "created_at",
    sort_order: str = "desc",
    page: int = 0,
    page_size: int = 10,
) -> dict[str, Any]:
    """构建通知页面上下文。"""
    current_lang = normalize_lang(lang)
    t = get_translations(current_lang)
    config_repo = NotificationConfigRepository()
    notification_repo = NotificationRepository()

    config_repo.ensure_all_scenes()

    normalized_scene = normalize_scene(scene)
    normalized_sort_by, normalized_sort_order = normalize_notification_sort(
        sort_by, sort_order
    )
    normalized_page = max(page, 0)
    normalized_page_size = min(max(page_size, 1), 100)

    notifications, total = list_notifications(
        session=session,
        scene=normalized_scene or None,
        account_id=account_id,
        is_read=is_read,
        q=q,
        sort_by=normalized_sort_by,
        sort_order=normalized_sort_order,
        page=normalized_page,
        page_size=normalized_page_size,
    )

    accounts = list(session.exec(select(Account).order_by(Account.id)).all())
    account_name_map = {
        account.id: (account.nickname or account.display_name or account.game_id)
        for account in accounts
        if account.id is not None
    }

    config_views = [build_config_view(config) for config in config_repo.get_all()]

    return {
        "t": t,
        "current_lang": current_lang,
        "notifications": notifications,
        "total": total,
        "unread_count": notification_repo.count_unread(),
        "scene_options": _build_scene_options(t),
        "selected_scene": normalized_scene,
        "selected_account_id": account_id,
        "selected_is_read": is_read,
        "q": q,
        "sort_by": normalized_sort_by,
        "sort_order": normalized_sort_order,
        "page": normalized_page,
        "page_size": normalized_page_size,
        "has_prev": normalized_page > 0,
        "has_next": (normalized_page + 1) * normalized_page_size < total,
        "accounts": accounts,
        "account_name_map": account_name_map,
        "configs": config_views,
        "task_type_options": get_task_type_options(),
        "task_status_options": TASK_STATUS_OPTIONS,
        "rarity_codes": list_rarity_codes(session),
    }


def build_recent_notifications_context(
    session: Session,
    lang: str,
    limit: int = 5,
) -> dict[str, Any]:
    """构建最近通知下拉内容上下文。"""
    current_lang = normalize_lang(lang)
    t = get_translations(current_lang)
    rows = list_recent_notifications(session, limit=limit)
    return {
        "t": t,
        "current_lang": current_lang,
        "notifications": rows,
    }
