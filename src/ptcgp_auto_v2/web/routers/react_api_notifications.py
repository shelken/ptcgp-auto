# -*- coding: utf-8 -*-
"""React API - 通知路由。"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlmodel import Session

from ptcgp_auto_v2.db.engine import get_fastapi_session
from ptcgp_auto_v2.infra.notifier import get_notifier
from ptcgp_auto_v2.web.routers.react_api_common import (
    json_response,
    parse_bool_flag,
    parse_unique_int_ids,
)
from ptcgp_auto_v2.web.services.notification_service import (
    TASK_STATUS_OPTIONS,
    build_notification_card_selector_context,
    build_notification_panel_context,
    build_notifications_context,
    get_notification_by_id,
    get_task_type_options,
    get_unread_notification_count,
    list_rarity_codes,
    mark_all_notifications_as_read,
    mark_notification_as_read,
    normalize_scene,
    update_notification_config,
)
from ptcgp_auto_v2.web.utils.filter_utils import normalize_page, normalize_page_size
from ptcgp_auto_v2.web.utils.form_utils import parse_optional_int
from ptcgp_auto_v2.web.utils.i18n import get_current_i18n


router = APIRouter()


@router.get("/notifications/count")
async def get_notifications_count():
    """获取顶部通知未读数量。"""
    return json_response({"unread_count": get_unread_notification_count()})


@router.get("/notifications/panel")
async def get_notifications_panel(
    page: int = Query(default=0),
    page_size: int = Query(default=10),
    session: Session = Depends(get_fastapi_session),
):
    """获取顶部通知抽屉数据。"""
    return json_response(
        build_notification_panel_context(
            session=session,
            page=normalize_page(page),
            page_size=normalize_page_size(page_size, max_size=50),
        )
    )


@router.post("/notifications/{notification_id}/mark-read")
async def post_mark_notification_read_for_panel(notification_id: int):
    """顶部通知抽屉：标记单条已读。"""
    mark_notification_as_read(notification_id)
    return json_response({"ok": True})


@router.post("/notifications/mark-all-read")
async def post_mark_all_notifications_read_for_panel(request: Request):
    """顶部通知抽屉：批量标记已读。"""
    body = await request.json()
    count = mark_all_notifications_as_read(
        scene=normalize_scene(body.get("scene")) or None,
        account_id=parse_optional_int(body.get("account_id")),
    )
    return json_response({"ok": True, "count": count})


@router.get("/management/notifications")
async def get_management_notifications(
    scene: str | None = Query(default=None),
    account_id: str | None = Query(default=None),
    is_read: str | None = Query(default=None),
    q: str = Query(default=""),
    sort_by: str = Query(default="created_at"),
    sort_order: str = Query(default="desc"),
    page: int = Query(default=0),
    page_size: int = Query(default=10),
    session: Session = Depends(get_fastapi_session),
):
    """获取通知管理页面数据。"""
    context = build_notifications_context(
        session=session,
        scene=normalize_scene(scene) or None,
        account_id=parse_optional_int(account_id),
        is_read=parse_bool_flag(is_read),
        q=q,
        sort_by=sort_by,
        sort_order=sort_order,
        page=normalize_page(page),
        page_size=normalize_page_size(page_size),
    )
    return json_response(context)


@router.post("/management/notifications/{notification_id}/mark-read")
async def post_mark_notification_read(notification_id: int):
    """标记通知已读。"""
    mark_notification_as_read(notification_id)
    return json_response({"ok": True})


@router.post("/management/notifications/mark-all-read")
async def post_mark_all_notifications_read(request: Request):
    """批量标记通知已读。"""
    body = await request.json()
    count = mark_all_notifications_as_read(
        scene=normalize_scene(body.get("scene")) or None,
        account_id=parse_optional_int(body.get("account_id")),
    )
    _, t = get_current_i18n()
    message_template = t.get("notification_marked_read") or "已标记 {count} 条通知为已读"
    return json_response(
        {
            "ok": True,
            "count": count,
            "message": message_template.format(count=count),
        }
    )


@router.post("/management/notifications/config")
async def post_notification_config(
    request: Request,
    session: Session = Depends(get_fastapi_session),
):
    """更新通知配置。"""
    body = await request.json()

    scene = normalize_scene(str(body.get("scene") or ""))
    if not scene:
        raise HTTPException(status_code=400, detail="invalid_scene")

    enabled = bool(body.get("enabled", False))
    enabled_webhook = bool(body.get("enabled_webhook", False))
    extra_config = body.get("extra_config")
    if not isinstance(extra_config, dict):
        extra_config = {}

    config = update_notification_config(
        scene=scene,
        enabled=enabled,
        enabled_webhook=enabled_webhook,
        extra_config=extra_config,
    )

    _, t = get_current_i18n()
    return json_response(
        {
            "ok": True,
            "message": t.get("notification_config_saved") or "配置已保存",
            "config": {
                "scene": config.scene,
                "enabled": config.enabled,
                "enabled_webhook": config.enabled_webhook,
                "extra_config": extra_config,
            },
            "task_type_options": get_task_type_options(),
            "task_status_options": TASK_STATUS_OPTIONS,
            "rarity_codes": list_rarity_codes(session),
        }
    )


@router.get("/management/notifications/card-picker")
async def get_management_notification_card_picker(
    request: Request,
    scene: str = Query(default="rare_card_obtained"),
    card_selector_q: str = Query(default=""),
    card_selector_rarity: str = Query(default=""),
    card_selector_set_code: str = Query(default=""),
    card_selector_pack_name: str = Query(default=""),
    card_selector_sort_by: str = Query(default="id"),
    card_selector_sort_order: str = Query(default="asc"),
    card_selector_page: int = Query(default=0),
    card_selector_page_size: int = Query(default=24),
    session: Session = Depends(get_fastapi_session),
):
    """获取通知配置卡牌选择器数据。"""
    selected_ids = parse_unique_int_ids(request.query_params.getlist("notify_card_ids"))
    context = build_notification_card_selector_context(
        session=session,
        scene=normalize_scene(scene) or "rare_card_obtained",
        selected_card_ids=selected_ids,
        q=card_selector_q,
        rarity=card_selector_rarity,
        set_code=card_selector_set_code,
        pack_name=card_selector_pack_name,
        sort_by=card_selector_sort_by,
        sort_order=card_selector_sort_order,
        page=normalize_page(card_selector_page),
        page_size=normalize_page_size(card_selector_page_size, max_size=60),
    )
    return json_response(context)


@router.post("/management/notifications/test-webhook")
async def post_notification_test_webhook(
    request: Request,
    session: Session = Depends(get_fastapi_session),
):
    """发送通知测试 Webhook。"""
    body = await request.json()
    notification_id = parse_optional_int(body.get("notification_id"))
    scene = normalize_scene(body.get("scene")) or None
    account_id = parse_optional_int(body.get("account_id"))
    q = str(body.get("q") or "")
    sort_by = str(body.get("sort_by") or "created_at")
    sort_order = str(body.get("sort_order") or "desc")
    page = parse_optional_int(body.get("page")) or 0
    page_size = parse_optional_int(body.get("page_size")) or 10
    parsed_is_read = parse_bool_flag(str(body.get("is_read") or ""))

    _, t = get_current_i18n()
    notification = None
    if notification_id is not None:
        notification = get_notification_by_id(notification_id)

    if notification is None:
        context = build_notifications_context(
            session=session,
            scene=scene,
            account_id=account_id,
            is_read=parsed_is_read,
            q=q,
            sort_by=sort_by,
            sort_order=sort_order,
            page=normalize_page(page),
            page_size=normalize_page_size(page_size),
        )
        notifications = context.get("notifications") or []
        notification = notifications[0] if notifications else None

    if notification is None:
        return json_response(
            {
                "ok": False,
                "message": t.get("webhook_test_empty") or "当前筛选下没有可测试通知",
            }
        )

    title = (
        notification.title
        if hasattr(notification, "title")
        else notification.get("title", "")
    )
    content = (
        notification.content
        if hasattr(notification, "content")
        else notification.get("content", "")
    )

    sent = get_notifier().send_webhook_notification(title=title, content=content)
    return json_response(
        {
            "ok": sent,
            "message": (
                t.get("webhook_test_success") if sent else t.get("webhook_test_failed")
            )
            or ("测试消息已发送" if sent else "测试发送失败，请检查 Webhook URL"),
        }
    )
