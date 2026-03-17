# -*- coding: utf-8 -*-
"""通知管理路由。"""

import json
from typing import Any

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import HTMLResponse
from sqlmodel import Session

from ptcgp_auto_v2.db.engine import get_fastapi_session
from ptcgp_auto_v2.infra.notifier import get_notifier
from ptcgp_auto_v2.web.services.notification_service import (
    TASK_STATUS_OPTIONS,
    build_config_view,
    build_notification_card_selector_context,
    build_notification_panel_context,
    build_notifications_context,
    build_recent_notifications_context,
    get_task_type_options,
    list_card_views_by_ids,
    list_rarity_codes,
    normalize_scene,
)
from ptcgp_auto_v2.web.utils.form_utils import parse_optional_int
from ptcgp_auto_v2.web.utils.i18n import get_current_i18n
from ptcgp_auto_v2.web.utils.response_utils import render_template

router = APIRouter()


def _parse_is_read_filter(is_read: str | None) -> bool | None:
    """将 is_read 查询参数解析为布尔值。"""
    if is_read == "true":
        return True
    if is_read == "false":
        return False
    return None


def _parse_unique_int_ids(values: list[str]) -> list[int]:
    """解析并去重整数 ID 列表，保留原顺序。"""
    parsed_ids: list[int] = []
    for item in values:
        if not str(item).isdigit():
            continue
        parsed = int(item)
        if parsed not in parsed_ids:
            parsed_ids.append(parsed)
    return parsed_ids


def _build_notification_list_filters(
    scene: str | None,
    account_id: str | None,
    is_read: str | None,
    q: str,
    sort_by: str,
    sort_order: str,
    page: int,
    page_size: int,
) -> dict[str, Any]:
    """标准化通知列表过滤参数。"""
    return {
        "scene": normalize_scene(scene) or None,
        "account_id": parse_optional_int(account_id),
        "is_read": _parse_is_read_filter(is_read),
        "q": q,
        "sort_by": sort_by,
        "sort_order": sort_order,
        "page": max(page, 0),
        "page_size": min(max(page_size, 1), 100),
    }


def _build_notifications_page_context(
    session: Session,
    filters: dict[str, Any],
) -> dict[str, Any]:
    """根据归一化过滤参数构建通知列表上下文。"""
    return build_notifications_context(
        session=session,
        scene=filters["scene"],
        account_id=filters["account_id"],
        is_read=filters["is_read"],
        q=filters["q"],
        sort_by=filters["sort_by"],
        sort_order=filters["sort_order"],
        page=filters["page"],
        page_size=filters["page_size"],
    )


async def _render_notification_page(
    request: Request,
    scene: str | None,
    account_id: str | None,
    is_read: str | None,
    q: str,
    sort_by: str,
    sort_order: str,
    page: int,
    page_size: int,
    session: Session,
    notification_view: str,
) -> HTMLResponse:
    """构建通知页面上下文并渲染统一模板。"""
    filters = _build_notification_list_filters(
        scene=scene,
        account_id=account_id,
        is_read=is_read,
        q=q,
        sort_by=sort_by,
        sort_order=sort_order,
        page=page,
        page_size=page_size,
    )
    context = _build_notifications_page_context(session, filters)
    context["notification_view"] = notification_view
    return render_template(request, "partials/notification_page.html", context)


@router.get("/management/notifications", response_class=HTMLResponse)
async def get_notifications_page(
    request: Request,
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
    """渲染通知管理页面（配置 + 列表）。"""
    return await _render_notification_page(
        request=request,
        scene=scene,
        account_id=account_id,
        is_read=is_read,
        q=q,
        sort_by=sort_by,
        sort_order=sort_order,
        page=page,
        page_size=page_size,
        session=session,
        notification_view="page",
    )


@router.get("/management/notifications/list", response_class=HTMLResponse)
async def get_notifications_list(
    request: Request,
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
    """渲染通知列表片段。"""
    return await _render_notification_page(
        request=request,
        scene=scene,
        account_id=account_id,
        is_read=is_read,
        q=q,
        sort_by=sort_by,
        sort_order=sort_order,
        page=page,
        page_size=page_size,
        session=session,
        notification_view="list",
    )


@router.get("/notifications/count", response_class=HTMLResponse)
async def get_unread_count(
    request: Request,
    session: Session = Depends(get_fastapi_session),
):
    """获取未读通知数量（用于顶部图标徽标）。"""
    from ptcgp_auto_v2.web.services.notification_service import (
        get_unread_notification_count,
    )

    count = get_unread_notification_count()
    if count <= 0:
        return ""
    return f'<span class="notification-badge brutal-tag status-badge status-chip status-tone-failed">{count}</span>'


@router.get("/notifications/recent", response_class=HTMLResponse)
async def get_recent_notifications(
    request: Request,
    limit: int = Query(default=5),
    session: Session = Depends(get_fastapi_session),
):
    """渲染最近通知列表片段。"""
    context = build_recent_notifications_context(
        session=session,
        limit=min(max(limit, 1), 20),
    )
    context["notification_view"] = "recent"
    return render_template(request, "partials/notification_page.html", context)


@router.get("/management/notifications/card-picker-modal", response_class=HTMLResponse)
async def get_notification_card_picker_modal(
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
    """渲染通知配置卡牌选择弹窗。"""
    selected_ids = _parse_unique_int_ids(
        request.query_params.getlist("notify_card_ids")
    )
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
        page=max(card_selector_page, 0),
        page_size=min(max(card_selector_page_size, 1), 60),
    )
    return render_template(request, "partials/modals/card_picker_modal.html", context)


@router.post("/management/notifications/card-picker/apply", response_class=HTMLResponse)
async def apply_notification_card_picker(
    request: Request,
    scene: str = Query(default="rare_card_obtained"),
    session: Session = Depends(get_fastapi_session),
):
    """应用卡牌选择结果并回填到配置表单。"""
    _, t = get_current_i18n()
    form = await request.form()
    selected_ids = _parse_unique_int_ids(form.getlist("notify_card_ids"))

    context = {
        "scene": normalize_scene(scene) or "rare_card_obtained",
        "selected_card_ids": selected_ids,
        "selected_cards": list_card_views_by_ids(session, selected_ids),
        "notification_view": "selected_cards",
    }
    response = render_template(request, "partials/notification_page.html", context)
    response.headers["HX-Trigger"] = json.dumps(
        {
            "closeModal": True,
            "showToast": {
                "message": t.get("notification_picker_applied") or "已应用卡牌选择"
            },
        },
        ensure_ascii=True,
    )
    return response


@router.post("/management/notifications/mark-read", response_class=HTMLResponse)
async def mark_as_read(
    request: Request,
    notification_id: int = Query(...),
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
    """标记单条通知为已读并刷新列表。"""
    from ptcgp_auto_v2.web.services.notification_service import (
        mark_notification_as_read,
    )

    mark_notification_as_read(notification_id)
    response = await get_notifications_list(
        request=request,
        scene=scene,
        account_id=account_id,
        is_read=is_read,
        q=q,
        sort_by=sort_by,
        sort_order=sort_order,
        page=page,
        page_size=page_size,
        session=session,
    )
    response.headers["HX-Trigger"] = json.dumps(
        {"notificationsUpdated": True}, ensure_ascii=True
    )
    return response


@router.post("/management/notifications/mark-all-read", response_class=HTMLResponse)
async def mark_all_as_read(
    request: Request,
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
    """批量标记已读并刷新列表。"""
    from ptcgp_auto_v2.web.services.notification_service import (
        mark_all_notifications_as_read,
    )

    _, t = get_current_i18n()
    filters = _build_notification_list_filters(
        scene=scene,
        account_id=account_id,
        is_read=is_read,
        q=q,
        sort_by=sort_by,
        sort_order=sort_order,
        page=page,
        page_size=page_size,
    )
    count = mark_all_notifications_as_read(
        scene=filters["scene"],
        account_id=filters["account_id"],
    )

    message_template = (
        t.get("notification_marked_read") or "已标记 {count} 条通知为已读"
    )
    message = message_template.format(count=count)
    response = await get_notifications_list(
        request=request,
        scene=scene,
        account_id=account_id,
        is_read=is_read,
        q=q,
        sort_by=sort_by,
        sort_order=sort_order,
        page=page,
        page_size=page_size,
        session=session,
    )
    response.headers["HX-Trigger"] = json.dumps(
        {
            "showToast": {"message": message},
            "notificationsUpdated": True,
        },
        ensure_ascii=True,
    )
    return response


@router.post("/management/notifications/config", response_class=HTMLResponse)
async def update_notification_config(
    request: Request,
    session: Session = Depends(get_fastapi_session),
):
    """更新通知配置。"""
    from ptcgp_auto_v2.web.services.notification_service import (
        update_notification_config as update_config,
    )

    _, t = get_current_i18n()
    form = await request.form()

    scene = normalize_scene(str(form.get("scene") or ""))
    if not scene:
        return HTMLResponse(content="", status_code=400)
    enabled = form.get("enabled") == "on"
    enabled_webhook = form.get("enabled_webhook") == "on"

    extra_config: dict[str, object] = {}
    if scene == "rare_card_obtained":
        notify_by_rarity = form.getlist("notify_by_rarity")
        notify_card_ids = _parse_unique_int_ids(form.getlist("notify_card_ids"))
        extra_config = {
            "notify_by_rarity": notify_by_rarity,
            "notify_card_ids": notify_card_ids,
        }
    elif scene == "task_status":
        notify_task_types = form.getlist("notify_task_types")
        notify_on = form.getlist("notify_on")
        extra_config = {
            "notify_task_types": notify_task_types,
            "notify_on": notify_on,
        }

    updated_config = update_config(
        scene=scene,
        enabled=enabled,
        enabled_webhook=enabled_webhook,
        extra_config=extra_config,
    )

    message = t.get("notification_config_saved") or "配置已保存"

    response = render_template(
        request,
        "partials/notification_page.html",
        {
            "config": build_config_view(updated_config),
            "task_type_options": get_task_type_options(),
            "task_status_options": TASK_STATUS_OPTIONS,
            "rarity_codes": list_rarity_codes(session),
            "notification_view": "config_item",
            "selected_card_ids": None,
            "selected_cards": None,
        },
    )
    response.headers["HX-Trigger"] = json.dumps(
        {"showToast": {"message": message}}, ensure_ascii=True
    )
    return response


@router.post("/management/notifications/test-webhook", response_class=HTMLResponse)
async def send_test_webhook(
    request: Request,
    notification_id: int | None = Query(default=None),
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
    """发送企业微信测试消息。"""
    from ptcgp_auto_v2.web.services.notification_service import get_notification_by_id

    _, t = get_current_i18n()

    notification = None
    if notification_id is not None:
        notification = get_notification_by_id(notification_id)
    else:
        filters = _build_notification_list_filters(
            scene=scene,
            account_id=account_id,
            is_read=is_read,
            q=q,
            sort_by=sort_by,
            sort_order=sort_order,
            page=page,
            page_size=page_size,
        )
        context = _build_notifications_page_context(session, filters)
        notifications = context.get("notifications") or []
        notification = notifications[0] if notifications else None

    if notification is None:
        message = t.get("webhook_test_empty") or "当前筛选下没有可测试通知"
        response = HTMLResponse(content="")
        response.headers["HX-Trigger"] = json.dumps(
            {"showToast": {"message": message}}, ensure_ascii=True
        )
        return response

    notifier = get_notifier()
    sent = notifier.send_webhook_notification(
        title=notification.title,
        content=notification.content,
    )

    message = (
        t.get("webhook_test_success") if sent else t.get("webhook_test_failed")
    ) or ("测试消息已发送" if sent else "测试发送失败，请检查 Webhook URL")

    response = HTMLResponse(content="")
    response.headers["HX-Trigger"] = json.dumps(
        {"showToast": {"message": message}}, ensure_ascii=True
    )
    return response


# ============================================================
# 通知面板 API（右侧滑出面板专用）
# ============================================================


@router.get("/notifications/panel", response_class=HTMLResponse)
async def get_notification_panel(
    request: Request,
    session: Session = Depends(get_fastapi_session),
):
    """
    渲染通知面板内容（首次加载）。

    排序规则：未读优先，同状态内按创建时间倒序。
    """
    context = build_notification_panel_context(
        session=session,
        page=0,
        page_size=10,
    )
    return render_template(request, "partials/notification_panel_content.html", context)


@router.get("/notifications/load-more", response_class=HTMLResponse)
async def get_notification_load_more(
    request: Request,
    page: int = Query(default=0),
    session: Session = Depends(get_fastapi_session),
):
    """
    渲染更多通知项（滚动加载）。

    用于 HTMX revealed trigger 无限滚动加载。
    """
    context = build_notification_panel_context(
        session=session,
        page=page,
        page_size=10,
    )
    return render_template(request, "partials/notification_list_items.html", context)


@router.post("/notifications/panel/mark-all-read", response_class=HTMLResponse)
async def mark_all_panel_notifications_read(
    request: Request,
    session: Session = Depends(get_fastapi_session),
):
    """
    标记所有未读通知为已读，返回更新后的面板内容。

    通过 HX-Trigger 通知前端刷新 Badge 并显示 toast 提示。
    """
    from ptcgp_auto_v2.web.services.notification_service import (
        mark_all_notifications_as_read,
    )

    _, t = get_current_i18n()

    count = mark_all_notifications_as_read()

    # 构建更新后的面板内容上下文
    context = build_notification_panel_context(
        session=session,
        page=0,
        page_size=10,
    )
    context["unread_count"] = 0  # 全部已读

    response = render_template(
        request, "partials/notification_list_items.html", context
    )

    # 通过 HX-Trigger 通知前端更新 badge 和显示 toast
    message_template = (
        t.get("notification_marked_read") or "已标记 {count} 条通知为已读"
    )
    message = message_template.format(count=count)
    response.headers["HX-Trigger"] = json.dumps(
        {
            "notificationsUpdated": True,
            "showToast": {"message": message},
        },
        ensure_ascii=True,
    )

    return response
