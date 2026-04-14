# -*- coding: utf-8 -*-
"""通知管理页面服务。"""

import json
import re
from dataclasses import dataclass
from typing import Any, Optional

from sqlmodel import Session, col, func, select

from ptcgp_auto_v2.config.assets import build_card_image_urls
from ptcgp_auto_v2.config.constants import (
    HIGH_RARITY_TARGETS,
)
from ptcgp_auto_v2.config.notification import (
    NOTIFICATION_SCENE_LABEL_KEYS,
    NOTIFICATION_SCENE_OPTIONS,
    NOTIFICATION_TASK_STATUS_OPTIONS,
)
from ptcgp_auto_v2.db.engine import session_scope
from ptcgp_auto_v2.db.models import (
    Account,
    Card,
    Notification,
)
from ptcgp_auto_v2.db.repositories import (
    CardRepository,
    NotificationConfigRepository,
    NotificationRepository,
)
from ptcgp_auto_v2.tasks import TaskRegistry
from ptcgp_auto_v2.web.queries.notification_queries import (
    list_notification_selectable_cards,
    list_notifications,
    normalize_card_picker_sort,
    normalize_notification_sort,
)
from ptcgp_auto_v2.web.services._list_query_state import build_list_query_state
from ptcgp_auto_v2.web.utils.filter_utils import (
    normalize_choice,
)
from ptcgp_auto_v2.web.utils.i18n import resolve_card_name_from_data, resolve_label_json
from ptcgp_auto_v2.web.utils.serialization import serialize_account

SCENE_OPTIONS = list(NOTIFICATION_SCENE_OPTIONS)
TASK_STATUS_OPTIONS = list(NOTIFICATION_TASK_STATUS_OPTIONS)
RARITY_ORDER = {code: index for index, code in enumerate(HIGH_RARITY_TARGETS, start=1)}


@dataclass(slots=True, frozen=True)
class NotificationConfigData:
    """通知配置纯数据。"""

    scene: str
    enabled: bool
    enabled_webhook: bool
    extra_config: str | None


@dataclass(slots=True, frozen=True)
class NotificationData:
    """通知纯数据。"""

    id: int
    scene: str
    title: str
    content: str
    related_account_id: int | None
    related_card_id: int | None
    related_task_instance_id: int | None
    is_read: bool
    created_at: Any


def _build_scene_options() -> list[dict[str, str]]:
    """构建场景下拉选项。"""
    from ptcgp_auto_v2.web.utils.i18n import get_current_i18n

    _, t = get_current_i18n()
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


def _to_notification_config_data(config) -> NotificationConfigData:
    """将通知配置模型转成纯数据。"""
    return NotificationConfigData(
        scene=config.scene,
        enabled=config.enabled,
        enabled_webhook=config.enabled_webhook,
        extra_config=config.extra_config,
    )


def build_config_view(config: NotificationConfigData) -> dict[str, Any]:
    """将通知配置模型转换为模板可用结构。"""
    return {
        "scene": config.scene,
        "enabled": config.enabled,
        "enabled_webhook": config.enabled_webhook,
        "extra_config": _safe_json_loads(config.extra_config),
    }


def normalize_scene(scene: str | None) -> str:
    """标准化通知场景参数。"""
    return normalize_choice(scene, allowed=set(SCENE_OPTIONS), default="")


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


def list_card_views_by_ids(
    session: Session, card_ids: list[int]
) -> list[dict[str, Any]]:
    """按给定顺序查询卡牌展示视图。"""
    return [_build_card_view(card) for card in list_cards_by_ids(session, card_ids)]


def _build_card_view(card: Card) -> dict[str, Any]:
    """构建卡牌展示视图（当前语言优先）。"""
    return {
        "id": card.id,
        "set_code": card.set_code,
        "number": card.number,
        "name": card.name,
        "display_name": resolve_card_name_from_data(card.data, fallback=card.name),
    }


def build_notification_card_selector_context(
    session: Session,
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
    normalized_sort_by, _ = normalize_card_picker_sort(
        sort_by, sort_order
    )
    list_state = build_list_query_state(
        q=q,
        sort_by=normalized_sort_by,
        sort_order=sort_order,
        page=page,
        page_size=page_size,
        max_page_size=60,
    )

    cards, total = list_notification_selectable_cards(
        session=session,
        q=list_state.normalized_q,
        rarity=rarity,
        set_code=set_code,
        pack_name=pack_name,
        sort_by=list_state.sort_by,
        sort_order=list_state.sort_order,
        page=list_state.page,
        page_size=list_state.page_size,
    )
    card_repo = CardRepository(session)
    set_options = [
        {
            "value": item.code,
            "display_name": resolve_label_json(item.label_data, fallback=item.code),
        }
        for item in card_repo.get_all_sets()
    ]
    pack_options = [
        {
            "value": item.name,
            "display_name": resolve_label_json(item.label_data, fallback=item.name),
        }
        for item in card_repo.get_all_packs()
        if item.name
    ]
    selected_card_rows = list_card_views_by_ids(session, selected_card_ids)
    card_rows = [_build_card_view(card) for card in cards]

    return {
        "scene": scene,
        "cards": card_rows,
        "selected_card_ids": selected_card_ids,
        "selected_cards": selected_card_rows,
        "card_selector_q": q,
        "card_selector_rarity": rarity,
        "card_selector_set_code": set_code,
        "card_selector_pack_name": pack_name,
        "card_selector_sort_by": list_state.sort_by,
        "card_selector_sort_order": list_state.sort_order,
        "card_selector_page": list_state.page,
        "card_selector_page_size": list_state.page_size,
        "card_selector_total": total,
        "card_selector_has_prev": list_state.has_prev,
        "card_selector_has_next": list_state.has_next(total=total),
        "filter_options": {
            "rarity": list_rarity_codes(session),
            "set_code": set_options,
            "pack_name": pack_options,
        },
        "rarity_codes": list_rarity_codes(session),
        "set_codes": set_options,
        "pack_names": pack_options,
    }


def build_notifications_context(
    session: Session,
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
    config_repo = NotificationConfigRepository(session)
    notification_repo = NotificationRepository(session)

    config_repo.ensure_all_scenes()

    normalized_scene = normalize_scene(scene)
    normalized_sort_by, _ = normalize_notification_sort(
        sort_by, sort_order
    )
    list_state = build_list_query_state(
        q=q,
        sort_by=normalized_sort_by,
        sort_order=sort_order,
        page=page,
        page_size=page_size,
    )

    notifications, total = list_notifications(
        session=session,
        scene=normalized_scene or None,
        account_id=account_id,
        is_read=is_read,
        q=list_state.normalized_q,
        sort_by=list_state.sort_by,
        sort_order=list_state.sort_order,
        page=list_state.page,
        page_size=list_state.page_size,
    )

    from ptcgp_auto_v2.web.utils.i18n import get_current_lang

    accounts = [
        serialize_account(account)
        for account in session.exec(select(Account).order_by(Account.id)).all()
    ]
    account_name_map = {
        account["id"]: (
            account["nickname"] or account["display_name"] or account["game_id"]
        )
        for account in accounts
        if account["id"] is not None
    }

    config_views = [
        build_config_view(_to_notification_config_data(config))
        for config in config_repo.get_all()
    ]
    scene_options = _build_scene_options()
    scene_label_map = {
        str(item["value"]): str(item["label"])
        for item in scene_options
        if isinstance(item, dict) and "value" in item and "label" in item
    }
    current_lang = get_current_lang()
    image_payload_map = _build_notification_image_payloads(
        notifications=notifications,
        session=session,
        lang=current_lang,
    )

    notifications_view = _build_notification_list_rows(
        notifications=notifications,
        image_payload_map=image_payload_map,
        scene_label_map=scene_label_map,
    )

    return {
        "notifications": notifications_view,
        "total": total,
        "unread_count": notification_repo.count_unread(),
        "filter_options": {
            "scene": scene_options,
            "task_type": get_task_type_options(),
            "task_status": TASK_STATUS_OPTIONS,
            "rarity_code": list_rarity_codes(session),
        },
        "scene_options": scene_options,
        "selected_scene": normalized_scene,
        "selected_account_id": account_id,
        "selected_is_read": is_read,
        "q": q,
        "sort_by": list_state.sort_by,
        "sort_order": list_state.sort_order,
        **list_state.page_meta(total=total),
        "accounts": accounts,
        "account_name_map": account_name_map,
        "configs": config_views,
        "task_type_options": get_task_type_options(),
        "task_status_options": TASK_STATUS_OPTIONS,
        "rarity_codes": list_rarity_codes(session),
    }


def _build_default_image_payload(content: str) -> dict[str, str | None]:
    """构建通知默认图片 payload。"""
    image_url = _extract_image_url(content)
    return {
        "image_url": image_url,
        "image_webp_url": _build_image_webp_fallback_url(image_url),
    }


def _build_notification_list_rows(
    *,
    notifications: list[Notification],
    image_payload_map: dict[int, dict[str, str | None]],
    scene_label_map: dict[str, str],
) -> list[dict[str, Any]]:
    """构建通知列表视图行。"""
    rows: list[dict[str, Any]] = []
    for item in notifications:
        row = item.model_dump()
        payload = image_payload_map.get(
            item.id,
            _build_default_image_payload(item.content),
        )
        row["scene_label"] = scene_label_map.get(item.scene, item.scene)
        row["image_url"] = payload.get("image_url")
        row["image_webp_url"] = payload.get("image_webp_url")
        rows.append(row)
    return rows

def build_notification_panel_context(
    session: Session,
    page: int = 0,
    page_size: int = 10,
) -> dict[str, Any]:
    """
    构建通知面板内容上下文。

    排序规则：
    - 未读通知优先显示
    - 同状态内按创建时间倒序

    Returns:
        dict: 包含 notifications, has_more, next_page, unread_count, total_count 等字段
    """
    from ptcgp_auto_v2.web.utils.i18n import get_current_lang

    list_state = build_list_query_state(
        sort_by="created_at",
        sort_order="desc",
        page=page,
        page_size=page_size,
        max_page_size=50,
    )
    notifications, unread_count, total_count = _list_panel_notifications(
        session=session,
        page=list_state.page,
        page_size=list_state.page_size,
    )
    has_more = list_state.has_next(total=total_count)
    next_page = list_state.page + 1 if has_more else list_state.page

    current_lang = get_current_lang()
    image_payload_map = _build_notification_image_payloads(
        notifications=notifications,
        session=session,
        lang=current_lang,
    )
    notification_dicts = _build_panel_notification_rows(
        notifications=notifications,
        image_payload_map=image_payload_map,
    )

    return {
        "notifications": notification_dicts,
        "has_more": has_more,
        "next_page": next_page,
        "unread_count": unread_count,
        "total_count": total_count,
        "page": list_state.page,
        "page_size": list_state.page_size,
    }


def _list_panel_notifications(
    *,
    session: Session,
    page: int,
    page_size: int,
) -> tuple[list[Notification], int, int]:
    """按未读优先规则查询面板通知。"""
    unread_stmt = (
        select(Notification)
        .where(Notification.is_read.is_(False))
        .order_by(col(Notification.created_at).desc())
    )
    read_stmt = (
        select(Notification)
        .where(Notification.is_read.is_(True))
        .order_by(col(Notification.created_at).desc())
    )
    offset = page * page_size
    unread_count_stmt = select(func.count()).select_from(unread_stmt.subquery())
    unread_count = int(session.exec(unread_count_stmt).one())

    notifications: list[Notification] = []
    if offset < unread_count:
        unread_offset = offset
        unread_limit = min(page_size, unread_count - unread_offset)
        unread_rows = list(
            session.exec(unread_stmt.offset(unread_offset).limit(unread_limit)).all()
        )
        notifications.extend(unread_rows)
        remaining = page_size - len(notifications)
        if remaining > 0:
            notifications.extend(list(session.exec(read_stmt.limit(remaining)).all()))
    else:
        read_offset = offset - unread_count
        notifications.extend(
            list(session.exec(read_stmt.offset(read_offset).limit(page_size)).all())
        )

    total_count_stmt = select(func.count()).select_from(Notification)
    total_count = int(session.exec(total_count_stmt).one())
    return notifications, unread_count, total_count


def _build_panel_notification_rows(
    *,
    notifications: list[Notification],
    image_payload_map: dict[int, dict[str, str | None]],
) -> list[dict[str, Any]]:
    """构建通知面板行数据。"""
    rows: list[dict[str, Any]] = []
    for notification in notifications:
        image_payload = image_payload_map.get(
            notification.id,
            _build_default_image_payload(notification.content),
        )
        rows.append(
            {
                "id": notification.id,
                "scene": notification.scene,
                "title": notification.title,
                "content": notification.content,
                "image_url": image_payload["image_url"],
                "image_webp_url": image_payload["image_webp_url"],
                "related_account_id": notification.related_account_id,
                "related_task_instance_id": notification.related_task_instance_id,
                "is_read": notification.is_read,
                "created_at": notification.created_at,
                "relative_time": _format_relative_time(notification.created_at),
            }
        )
    return rows


def _extract_image_url(content: str) -> str | None:
    """从 Markdown 内容中提取第一个图片 URL。"""
    if not content:
        return None
    # 匹配 ![alt](url) 格式
    match = re.search(r"!\[.*?\]\((https?://[^\)]+)\)", content)
    if match:
        return match.group(1)
    return None

def _build_notification_image_payloads(
    notifications: list[Notification],
    session: Session,
    lang: str,
) -> dict[int, dict[str, str | None]]:
    """批量构建通知图片 URL，避免逐条查询导致 N+1。"""
    payload_map: dict[int, dict[str, str | None]] = {}
    parsed_map: dict[int, tuple[str, str]] = {}
    card_id_map: dict[int, int] = {}

    for notification in notifications:
        payload_map[notification.id] = _build_default_image_payload(
            notification.content
        )
        if notification.scene != "rare_card_obtained":
            continue
        if notification.related_card_id:
            card_id_map[notification.id] = int(notification.related_card_id)
            continue
        parsed = _extract_card_name_and_rarity(notification.content or "")
        if parsed:
            parsed_map[notification.id] = parsed

    _apply_related_card_id_payloads(
        payload_map=payload_map,
        card_id_map=card_id_map,
        session=session,
        lang=lang,
    )
    _apply_parsed_card_payloads(
        payload_map=payload_map,
        parsed_map=parsed_map,
        session=session,
        lang=lang,
    )
    return payload_map


def _apply_related_card_id_payloads(
    *,
    payload_map: dict[int, dict[str, str | None]],
    card_id_map: dict[int, int],
    session: Session,
    lang: str,
) -> None:
    """按 related_card_id 覆盖通知图片 payload。"""
    if not card_id_map:
        return
    card_ids = sorted(set(card_id_map.values()))
    cards = list(session.exec(select(Card).where(col(Card.id).in_(card_ids))).all())
    card_by_id = {card.id: card for card in cards if card.id is not None}
    for notification_id, card_id in card_id_map.items():
        card = card_by_id.get(card_id)
        if card is None or not card.set_code or card.number is None:
            continue
        image_url, image_webp_url = build_card_image_urls(
            set_code=card.set_code,
            card_number=card.number,
            lang=lang,
            width=400,
        )
        payload_map[notification_id] = {
            "image_url": image_url,
            "image_webp_url": image_webp_url,
        }


def _apply_parsed_card_payloads(
    *,
    payload_map: dict[int, dict[str, str | None]],
    parsed_map: dict[int, tuple[str, str]],
    session: Session,
    lang: str,
) -> None:
    """按通知文案解析结果覆盖通知图片 payload。"""
    if not parsed_map:
        return
    card_names = sorted({card_name for card_name, _ in parsed_map.values()})
    if not card_names:
        return

    cards = list(session.exec(select(Card).where(col(Card.name).in_(card_names))).all())
    cards_by_name: dict[str, list[Card]] = {}
    for card in cards:
        cards_by_name.setdefault(card.name, []).append(card)

    for notification_id, (card_name, rarity_code) in parsed_map.items():
        candidates = cards_by_name.get(card_name, [])
        target_card = next(
            (card for card in candidates if card.rarity == rarity_code),
            candidates[0] if candidates else None,
        )
        if target_card is None or not target_card.set_code or target_card.number is None:
            continue
        image_url, image_webp_url = build_card_image_urls(
            set_code=target_card.set_code,
            card_number=target_card.number,
            lang=lang,
            width=400,
        )
        payload_map[notification_id] = {
            "image_url": image_url,
            "image_webp_url": image_webp_url,
        }


def _extract_card_name_and_rarity(content: str) -> tuple[str, str] | None:
    """从通知内容提取卡牌名与稀有度编码。"""
    card_name = ""
    rarity_code = ""
    for line in (content or "").splitlines():
        text = line.strip()
        if text.startswith("卡牌:"):
            card_name = text.split(":", 1)[1].strip()
        elif text.startswith("稀有度:"):
            rarity_text = text.split(":", 1)[1].strip()
            rarity_code = rarity_text.split(" ", 1)[0].strip()

    if card_name and rarity_code:
        return card_name, rarity_code

    legacy_match = re.search(
        r"\*\*(?P<rarity>[A-Z]+)\s+(?P<name>[^*]+)\*\*", content or ""
    )
    if legacy_match:
        return legacy_match.group("name").strip(), legacy_match.group("rarity").strip()

    return None

def _build_image_webp_fallback_url(image_url: str | None) -> str | None:
    """基于原图 URL 生成 webp 回退地址。"""
    if not image_url:
        return None

    # 与 owned-card 保持一致：wsrv output 参数优先改为 webp
    if "output=png" in image_url:
        return image_url.replace("output=png", "output=webp")

    # 兜底：常见 png 扩展名回退到 webp
    if image_url.endswith(".png"):
        return image_url[:-4] + ".webp"

    return image_url


def _format_relative_time(created_at: Any) -> str:
    """格式化相对时间文本。"""
    from datetime import datetime

    from ptcgp_auto_v2.web.utils.i18n import get_current_i18n

    if created_at is None:
        return ""

    current_lang, t = get_current_i18n()

    # 确保使用本地时间
    now = datetime.now()
    diff_ms = (now - created_at).total_seconds() * 1000

    if diff_ms < 0:
        # 未来时间
        abs_sec = abs(diff_ms) / 1000
        if abs_sec < 60:
            return t.get("relative_soon") or "soon"
        return _format_time_value(abs_sec, current_lang, t, future=True)

    abs_sec = diff_ms / 1000

    if abs_sec < 60:
        return t.get("relative_just_now") or "just now"

    return _format_time_value(abs_sec, current_lang, t, future=False)


def _format_time_value(
    abs_sec: float,
    lang: str,
    t: dict[str, Any],
    future: bool,
) -> str:
    """格式化时间值。"""
    if abs_sec < 3600:
        value = round(abs_sec / 60)
        unit = t.get("relative_minutes") or "min"
    elif abs_sec < 86400:
        value = round(abs_sec / 3600)
        unit = t.get("relative_hours") or "hr"
    else:
        value = round(abs_sec / 86400)
        unit = t.get("relative_days") or "day"

    ago_text = t.get("relative_ago") or "ago"
    in_text = t.get("relative_in") or "in"

    if lang.startswith("en"):
        return f"{in_text} {value} {unit}" if future else f"{value} {unit} {ago_text}"

    return f"{value}{unit}{in_text}" if future else f"{value}{unit}{ago_text}"


def mark_notification_as_read(notification_id: int) -> None:
    """标记单条通知为已读。"""
    with session_scope() as session:
        NotificationRepository(session).mark_as_read(notification_id)


def mark_all_notifications_as_read(
    scene: str | None = None,
    account_id: int | None = None,
) -> int:
    """批量标记通知为已读。

    Returns:
        标记为已读的通知数量
    """
    with session_scope() as session:
        return NotificationRepository(session).mark_all_as_read(
            scene=scene,
            account_id=account_id,
        )


def get_unread_notification_count() -> int:
    """获取未读通知数量。"""
    with session_scope() as session:
        return NotificationRepository(session).count_unread()


def update_notification_config(
    scene: str,
    enabled: bool,
    enabled_webhook: bool,
    extra_config: dict[str, object],
) -> NotificationConfigData:
    """更新通知配置。

    Returns:
        更新后的配置对象
    """
    with session_scope() as session:
        config_repo = NotificationConfigRepository(session)
        updated = config_repo.update(
            scene=scene,
            enabled=enabled,
            enabled_webhook=enabled_webhook,
            extra_config=extra_config,
        )
        if updated is None:
            raise RuntimeError(f"通知配置不存在: {scene}")

    with session_scope() as session:
        config = NotificationConfigRepository(session).get_or_create(scene)
        if config.scene != scene:
            raise RuntimeError(f"通知配置读取失败: {scene}")
        return _to_notification_config_data(config)


def get_notification_by_id(notification_id: int) -> NotificationData | None:
    """根据 ID 获取单条通知。

    Args:
        notification_id: 通知 ID

    Returns:
        通知对象，不存在则返回 None
    """
    with session_scope() as session:
        notification = NotificationRepository(session).get_by_id(notification_id)
        if notification is None or notification.id is None:
            return None
        return NotificationData(
            id=notification.id,
            scene=notification.scene,
            title=notification.title,
            content=notification.content,
            related_account_id=notification.related_account_id,
            related_card_id=notification.related_card_id,
            related_task_instance_id=notification.related_task_instance_id,
            is_read=notification.is_read,
            created_at=notification.created_at,
        )
