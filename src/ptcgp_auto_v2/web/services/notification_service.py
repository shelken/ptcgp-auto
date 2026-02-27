# -*- coding: utf-8 -*-
"""通知管理页面服务。"""

import json
import re
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
from ptcgp_auto_v2.db.models import (
    Account,
    Card,
    Notification,
    NotificationConfig,
    Pack,
)
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

SCENE_OPTIONS = list(NOTIFICATION_SCENE_OPTIONS)
TASK_STATUS_OPTIONS = list(NOTIFICATION_TASK_STATUS_OPTIONS)
RARITY_ORDER = {code: index for index, code in enumerate(HIGH_RARITY_TARGETS, start=1)}


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
        "notifications": notifications,
        "total": total,
        "unread_count": notification_repo.count_unread(),
        "scene_options": _build_scene_options(),
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
    limit: int = 5,
) -> dict[str, Any]:
    """构建最近通知下拉内容上下文。"""
    rows = list_recent_notifications(session, limit=limit)
    return {
        "notifications": rows,
    }


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
        dict: 包含 notifications, has_more, next_page, unread_count 等字段
    """
    from ptcgp_auto_v2.web.utils.i18n import get_current_lang

    notification_repo = NotificationRepository()

    normalized_page = max(page, 0)
    normalized_page_size = min(max(page_size, 1), 50)

    # 查询未读优先的通知列表
    # 使用两阶段查询：先获取未读，再获取已读
    unread_stmt = (
        select(Notification)
        .where(Notification.is_read == False)  # noqa: E712
        .order_by(col(Notification.created_at).desc())
    )

    read_stmt = (
        select(Notification)
        .where(Notification.is_read == True)  # noqa: E712
        .order_by(col(Notification.created_at).desc())
    )

    # 计算分页偏移
    offset = normalized_page * normalized_page_size

    # 获取未读数量，用于判断分页边界
    unread_count_stmt = select(func.count()).select_from(unread_stmt.subquery())
    unread_count = int(session.exec(unread_count_stmt).one())

    # 根据分页位置，从两个查询中组合数据
    notifications = []

    if offset < unread_count:
        # 当前页起始位置在未读区域内
        unread_offset = offset
        unread_limit = min(normalized_page_size, unread_count - unread_offset)
        unread_rows = list(
            session.exec(unread_stmt.offset(unread_offset).limit(unread_limit)).all()
        )
        notifications.extend(unread_rows)

        # 如果未读数据不够，从已读数据补充
        remaining = normalized_page_size - len(notifications)
        if remaining > 0:
            read_rows = list(session.exec(read_stmt.limit(remaining)).all())
            notifications.extend(read_rows)
    else:
        # 当前页起始位置在已读区域内
        read_offset = offset - unread_count
        read_rows = list(
            session.exec(
                read_stmt.offset(read_offset).limit(normalized_page_size)
            ).all()
        )
        notifications.extend(read_rows)

    # 计算总数和是否还有更多
    total_count_stmt = select(func.count()).select_from(Notification)
    total_count = int(session.exec(total_count_stmt).one())
    has_more = (normalized_page + 1) * normalized_page_size < total_count
    next_page = normalized_page + 1 if has_more else normalized_page

    # 转换为字典并添加相对时间文本和图片URL
    current_lang = get_current_lang()
    notification_dicts = []
    for n in notifications:
        image_payload = build_notification_image_payload(
            notification=n,
            session=session,
            lang=current_lang,
        )

        notification_dicts.append(
            {
                "id": n.id,
                "scene": n.scene,
                "title": n.title,
                "content": n.content,
                "image_url": image_payload["image_url"],
                "image_webp_url": image_payload["image_webp_url"],
                "related_account_id": n.related_account_id,
                "related_task_instance_id": n.related_task_instance_id,
                "is_read": n.is_read,
                "created_at": n.created_at,
                "relative_time": _format_relative_time(n.created_at),
            }
        )

    return {
        "notifications": notification_dicts,
        "has_more": has_more,
        "next_page": next_page,
        "unread_count": unread_count,
        "page": normalized_page,
        "page_size": normalized_page_size,
    }


def _extract_image_url(content: str) -> str | None:
    """从 Markdown 内容中提取第一个图片 URL。"""
    if not content:
        return None
    # 匹配 ![alt](url) 格式
    match = re.search(r"!\[.*?\]\((https?://[^\)]+)\)", content)
    if match:
        return match.group(1)
    return None


def build_notification_image_payload(
    notification: Notification,
    session: Session,
    lang: str,
) -> dict[str, str | None]:
    """统一构造通知图片 URL（普通 markdown / 稀有卡牌同源规则）。"""
    image_url = _extract_image_url(notification.content)
    image_webp_url = _build_image_webp_fallback_url(image_url)

    card_image_url, card_image_webp_url = _build_notification_card_asset_urls(
        notification=notification,
        session=session,
        lang=lang,
    )
    if card_image_url:
        image_url = card_image_url
        image_webp_url = card_image_webp_url

    return {
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


def _build_notification_card_asset_urls(
    notification: Notification,
    session: Session,
    lang: str,
) -> tuple[str | None, str | None]:
    """按拥有卡同源规则生成通知缩略图 URL（png + webp）。"""
    if notification.scene != "rare_card_obtained":
        return None, None

    parsed = _extract_card_name_and_rarity(notification.content or "")
    if not parsed:
        return None, None

    card_name, rarity_code = parsed
    card = session.exec(
        select(Card).where(Card.name == card_name, Card.rarity == rarity_code)
    ).first()
    if card is None:
        card = session.exec(select(Card).where(Card.name == card_name)).first()
    if card is None or not card.set_code or card.number is None:
        return None, None

    return build_card_image_urls(
        set_code=card.set_code,
        card_number=card.number,
        lang=lang,
        width=400,
    )


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
    repo = NotificationRepository()
    repo.mark_as_read(notification_id)


def mark_all_notifications_as_read(
    scene: str | None = None,
    account_id: int | None = None,
) -> int:
    """批量标记通知为已读。

    Returns:
        标记为已读的通知数量
    """
    repo = NotificationRepository()
    return repo.mark_all_as_read(scene=scene, account_id=account_id)


def get_unread_notification_count() -> int:
    """获取未读通知数量。"""
    repo = NotificationRepository()
    return repo.count_unread()


def update_notification_config(
    scene: str,
    enabled: bool,
    enabled_webhook: bool,
    extra_config: dict[str, object],
) -> NotificationConfig:
    """更新通知配置。

    Returns:
        更新后的配置对象
    """
    config_repo = NotificationConfigRepository()
    config_repo.update(
        scene=scene,
        enabled=enabled,
        enabled_webhook=enabled_webhook,
        extra_config=extra_config,
    )
    return config_repo.get_or_create(scene)


def get_notification_by_id(notification_id: int) -> Notification | None:
    """根据 ID 获取单条通知。

    Args:
        notification_id: 通知 ID

    Returns:
        通知对象，不存在则返回 None
    """
    repo = NotificationRepository()
    return repo.get_by_id(notification_id)
