# -*- coding: utf-8 -*-
"""React 前端专用 API 路由。"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse
from sqlmodel import Session

from ptcgp_auto_v2.core.scheduling_service import (
    TASK_SORT_BY_DISPATCH_PRIORITY,
    normalize_task_sort,
)
from ptcgp_auto_v2.db.engine import get_fastapi_session
from ptcgp_auto_v2.db.models import Account
from ptcgp_auto_v2.infra.notifier import get_notifier
from ptcgp_auto_v2.web.services.account_service import (
    build_account_edit_context,
    build_account_plans_context,
    build_accounts_list_context,
    update_account_details,
    update_account_plans,
)
from ptcgp_auto_v2.web.services.daily_gift_service import build_daily_gift_context
from ptcgp_auto_v2.web.services.exchange_card_service import (
    build_exchange_card_context,
    cancel_exchange_request,
    create_exchange_request_with_task,
)
from ptcgp_auto_v2.web.services.friendship_service import (
    build_friendship_context,
    cancel_pending_request,
    create_add_request,
    create_delete_request,
)
from ptcgp_auto_v2.web.services.metadata_service import (
    build_metadata_context,
    check_metadata_sources,
    execute_metadata_sync,
    preview_metadata_sync,
)
from ptcgp_auto_v2.web.services.notification_service import (
    TASK_STATUS_OPTIONS,
    build_notification_card_selector_context,
    build_notification_panel_context,
    build_notifications_context,
    get_unread_notification_count,
    get_notification_by_id,
    get_task_type_options,
    list_rarity_codes,
    mark_all_notifications_as_read,
    mark_notification_as_read,
    normalize_scene,
    update_notification_config,
)
from ptcgp_auto_v2.web.services.owned_card_service import (
    build_owned_card_exchange_accounts_context,
    build_owned_card_modal_context,
    build_owned_cards_list_context,
    build_owned_cards_progress_context,
)
from ptcgp_auto_v2.web.services.pack_config_service import (
    build_card_sets_options,
    build_pack_config_context,
    build_save_account_pack_config,
    build_set_boosters_options,
)
from ptcgp_auto_v2.web.services.plan_service import (
    build_plan_edit_context,
    build_plans_list_context,
    delete_plan_by_id,
    upsert_plan_from_form,
)
from ptcgp_auto_v2.web.services.record_service import build_records_list_context
from ptcgp_auto_v2.web.services.resource_service import build_resources_context
from ptcgp_auto_v2.web.services.task_service import (
    build_task_list_render_context,
    list_task_filter_accounts,
    reset_completed_tasks_by_filters,
)
from ptcgp_auto_v2.web.utils.filter_utils import normalize_page, normalize_page_size
from ptcgp_auto_v2.web.utils.form_utils import parse_optional_int
from ptcgp_auto_v2.web.utils.i18n import get_current_i18n


router = APIRouter(prefix="/api/react", tags=["react-api"])


def _json(payload: Any) -> JSONResponse:
    """统一 JSON 输出。"""
    return JSONResponse(content=jsonable_encoder(payload))


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


@router.get("/notifications/count")
async def get_notifications_count():
    """获取顶部通知未读数量。"""
    return _json({"unread_count": get_unread_notification_count()})


@router.get("/notifications/panel")
async def get_notifications_panel(
    page: int = Query(default=0),
    page_size: int = Query(default=10),
    session: Session = Depends(get_fastapi_session),
):
    """获取顶部通知抽屉数据。"""
    return _json(
        build_notification_panel_context(
            session=session,
            page=max(page, 0),
            page_size=min(max(page_size, 1), 50),
        )
    )


@router.post("/notifications/{notification_id}/mark-read")
async def post_mark_notification_read_for_panel(notification_id: int):
    """顶部通知抽屉：标记单条已读。"""
    mark_notification_as_read(notification_id)
    return _json({"ok": True})


@router.post("/notifications/mark-all-read")
async def post_mark_all_notifications_read_for_panel(request: Request):
    """顶部通知抽屉：批量标记已读。"""
    body = await request.json()
    count = mark_all_notifications_as_read(
        scene=normalize_scene(body.get("scene")) or None,
        account_id=parse_optional_int(body.get("account_id")),
    )
    return _json({"ok": True, "count": count})


@router.get("/records")
async def get_records(
    page: int = Query(default=0),
    page_size: int = Query(default=10),
    rarity: list[str] = Query(default=[]),
    card_type: list[str] = Query(default=[]),
    session: Session = Depends(get_fastapi_session),
):
    """获取开包记录数据。"""
    context = build_records_list_context(
        session=session,
        page=normalize_page(page),
        page_size=normalize_page_size(page_size),
        rarity=[item for item in rarity if item],
        card_type=[item for item in card_type if item],
    )
    return _json(context)


@router.get("/owned-cards")
async def get_owned_cards(
    page: int = Query(default=0),
    page_size: int = Query(default=60),
    account_id: str | None = Query(default=None),
    rarity: list[str] = Query(default=[]),
    card_type: list[str] = Query(default=[]),
    set_code: list[str] = Query(default=[]),
    pack_name: list[str] = Query(default=[]),
    element: list[str] = Query(default=[]),
    sort_by: str = Query(default="acquired"),
    ownership_scope: str = Query(default="owned"),
    session: Session = Depends(get_fastapi_session),
):
    """获取拥有卡牌列表数据。"""
    context = build_owned_cards_list_context(
        session=session,
        page=page,
        page_size=page_size,
        account_id=account_id,
        rarity=rarity,
        card_type=card_type,
        set_code=set_code,
        pack_name=pack_name,
        element=element,
        sort_by=sort_by,
        ownership_scope=ownership_scope,
    )
    return _json(context)


@router.get("/owned-cards/stats")
async def get_owned_cards_stats(
    account_id: str | None = Query(default=None),
    rarity: list[str] = Query(default=[]),
    card_type: list[str] = Query(default=[]),
    set_code: list[str] = Query(default=[]),
    pack_name: list[str] = Query(default=[]),
    element: list[str] = Query(default=[]),
    ownership_scope: str = Query(default="owned"),
):
    """获取拥有卡牌统计。"""
    context = build_owned_cards_progress_context(
        account_id=account_id,
        rarity=rarity,
        card_type=card_type,
        set_code=set_code,
        pack_name=pack_name,
        element=element,
        ownership_scope=ownership_scope,
    )
    return _json(context)


@router.get("/owned-cards/{card_id}/detail")
async def get_owned_card_detail(
    card_id: int,
    ownership_state: str = Query(default="owned"),
    page_size: int = Query(default=10),
    session: Session = Depends(get_fastapi_session),
):
    """获取卡牌详情和交换账号数据。"""
    context = build_owned_card_modal_context(
        session=session,
        card_id=card_id,
        page_size=page_size,
        ownership_state=ownership_state,
    )
    if context is None:
        raise HTTPException(status_code=404, detail="card_not_found")
    return _json(context)


@router.get("/owned-cards/{card_id}/exchange-accounts")
async def get_owned_card_exchange_accounts(
    card_id: int,
    page: int = Query(default=0),
    page_size: int = Query(default=10),
    q: str = Query(default=""),
    sort_by: str = Query(default="account_id"),
    sort_order: str = Query(default="asc"),
    session: Session = Depends(get_fastapi_session),
):
    """获取卡牌交换账号分页数据。"""
    context = build_owned_card_exchange_accounts_context(
        session=session,
        card_id=card_id,
        page=page,
        page_size=page_size,
        q=q,
        sort_by=sort_by,
        sort_order=sort_order,
    )
    return _json(context)


@router.post("/exchange-cards/requests")
async def create_exchange_request(request: Request):
    """创建交换请求。"""
    body = await request.json()
    from_account_id = parse_optional_int(body.get("from_account_id"))
    to_account_id = parse_optional_int(body.get("to_account_id"))
    target_card_id = parse_optional_int(body.get("target_card_id"))
    to_friend_id = str(body.get("to_friend_id") or "").strip()
    target_card_rarity = str(body.get("target_card_rarity") or "")

    ok = False
    if from_account_id and target_card_id and to_friend_id:
        ok = create_exchange_request_with_task(
            from_account_id=from_account_id,
            to_account_id=to_account_id,
            to_friend_id=to_friend_id,
            target_card_id=target_card_id,
            target_card_rarity=target_card_rarity,
        )

    _, t = get_current_i18n()
    return _json(
        {
            "ok": ok,
            "message": (
                t.get("msg_exchange_request_created")
                if ok
                else t.get("msg_exchange_request_skipped")
            )
            or ("交换请求已创建" if ok else "交换请求创建失败"),
        }
    )


@router.get("/management/accounts")
async def get_management_accounts(
    q: str = Query(default=""),
    sort_by: str = Query(default="id"),
    sort_order: str = Query(default="asc"),
    page: int = Query(default=0),
    page_size: int = Query(default=10),
    session: Session = Depends(get_fastapi_session),
):
    """获取账号管理数据。"""
    return _json(
        build_accounts_list_context(
            session=session,
            q=q,
            sort_by=sort_by,
            sort_order=sort_order,
            page=page,
            page_size=page_size,
        )
    )


@router.get("/management/accounts/{account_id}")
async def get_management_account(account_id: int):
    """获取账号编辑数据。"""
    context = build_account_edit_context(account_id)
    if context is None:
        raise HTTPException(status_code=404, detail="account_not_found")
    return _json(context)


@router.put("/management/accounts/{account_id}")
async def update_management_account(request: Request, account_id: int):
    """更新账号信息。"""
    body = await request.json()
    nickname = str(body.get("nickname") or "")
    remark = str(body.get("remark") or "")
    update_account_details(account_id, nickname, remark)
    _, t = get_current_i18n()
    return _json({"ok": True, "message": t.get("msg_saved") or "已保存"})


@router.get("/management/accounts/{account_id}/plans")
async def get_account_plans(
    account_id: int,
    session: Session = Depends(get_fastapi_session),
):
    """获取账号计划关联数据。"""
    context = build_account_plans_context(session, account_id)
    if context is None:
        raise HTTPException(status_code=404, detail="account_not_found")
    return _json(context)


@router.put("/management/accounts/{account_id}/plans")
async def put_account_plans(request: Request, account_id: int):
    """更新账号计划关联。"""
    data = await request.json()
    if not isinstance(data, list):
        raise HTTPException(status_code=400, detail="invalid_payload")
    update_account_plans(account_id, data)
    return _json({"ok": True})


@router.get("/management/accounts/{account_id}/pack-config")
async def get_account_pack_config(account_id: int):
    """获取账号开包配置。"""
    return _json(build_pack_config_context(account_id))


@router.put("/management/accounts/{account_id}/pack-config")
async def put_account_pack_config(request: Request, account_id: int):
    """保存账号开包配置。"""
    body = await request.json()
    set_code = str(body.get("set_code") or "")
    booster_name = str(body.get("booster_name") or "")
    build_save_account_pack_config(account_id, set_code, booster_name)
    _, t = get_current_i18n()
    return _json({"ok": True, "message": t.get("msg_saved") or "已保存"})


@router.get("/management/card-sets")
async def get_card_sets():
    """获取卡包系列。"""
    return _json(build_card_sets_options())


@router.get("/management/card-sets/{set_code}/boosters")
async def get_set_boosters(set_code: str):
    """获取系列补充包。"""
    return _json(build_set_boosters_options(set_code))


@router.get("/management/plans")
async def get_management_plans(
    q: str = Query(default=""),
    sort_by: str = Query(default="id"),
    sort_order: str = Query(default="asc"),
    page: int = Query(default=0),
    page_size: int = Query(default=10),
    session: Session = Depends(get_fastapi_session),
):
    """获取计划管理数据。"""
    return _json(
        build_plans_list_context(
            session=session,
            q=q,
            sort_by=sort_by,
            sort_order=sort_order,
            page=page,
            page_size=page_size,
        )
    )


@router.get("/management/plans/edit")
async def get_plan_edit(plan_id: int | None = Query(default=None)):
    """获取计划编辑数据。"""
    return _json(build_plan_edit_context(plan_id))


@router.post("/management/plans")
async def save_plan(request: Request):
    """保存计划。"""
    form = await request.form()
    duplicate_name = upsert_plan_from_form(form)
    if duplicate_name:
        _, t = get_current_i18n()
        msg_tpl = t.get("msg_plan_name_duplicate", "Plan name '{name}' already exists")
        return _json(
            {
                "ok": False,
                "message": msg_tpl.replace("{name}", duplicate_name),
                "error": "duplicate_name",
            }
        )
    _, t = get_current_i18n()
    return _json({"ok": True, "message": t.get("msg_saved") or "已保存"})


@router.delete("/management/plans/{plan_id}")
async def delete_plan(plan_id: int):
    """删除计划。"""
    delete_plan_by_id(plan_id)
    _, t = get_current_i18n()
    return _json({"ok": True, "message": t.get("msg_deleted") or "已删除"})


@router.get("/management/resources")
async def get_management_resources(
    view: str = Query(default="stats"),
    q: str = Query(default=""),
    sort_by: str = Query(default="id"),
    sort_order: str = Query(default="asc"),
    page: int = Query(default=0),
    page_size: int = Query(default=20),
    session: Session = Depends(get_fastapi_session),
):
    """获取资源管理数据。"""
    return _json(
        build_resources_context(
            session=session,
            view=view,
            q=q,
            sort_by=sort_by,
            sort_order=sort_order,
            page=page,
            page_size=page_size,
        )
    )


@router.get("/management/tasks")
async def get_management_tasks(
    status: list[str] = Query(default=[]),
    task_type: list[str] = Query(default=[]),
    account_id: str | None = Query(default=None),
    account_q: str = Query(default=""),
    page: int = Query(default=0),
    page_size: int = Query(default=10),
    sort_by: str = Query(default=TASK_SORT_BY_DISPATCH_PRIORITY),
    sort_order: str = Query(default="asc"),
    session: Session = Depends(get_fastapi_session),
):
    """获取任务管理数据。"""
    parsed_account_id: int | None = None
    if account_id:
        val = account_id.strip()
        if val.isdigit():
            parsed_account_id = int(val)

    normalized_status = [item for item in status if item]
    normalized_task_type = [item for item in task_type if item]
    sort_by, sort_order = normalize_task_sort(sort_by, sort_order)

    return _json(
        build_task_list_render_context(
            session=session,
            page=normalize_page(page),
            page_size=normalize_page_size(page_size),
            status=normalized_status,
            task_type=normalized_task_type,
            account_id=parsed_account_id,
            account_q=account_q,
            sort_by=sort_by,
            sort_order=sort_order,
            table_only=False,
        )
    )


@router.get("/management/tasks/account-options")
async def get_task_account_options(
    q: str = Query(default=""),
    session: Session = Depends(get_fastapi_session),
):
    """获取任务筛选账号候选。"""
    return _json({"accounts": list_task_filter_accounts(session=session, q=q, limit=20)})


@router.post("/management/tasks/reset-completed")
async def post_reset_completed_tasks(
    request: Request,
    session: Session = Depends(get_fastapi_session),
):
    """按筛选条件重置已完成任务。"""
    body = await request.json()
    status = [item for item in body.get("status", []) if isinstance(item, str) and item]
    task_type = [
        item for item in body.get("task_type", []) if isinstance(item, str) and item
    ]
    account_id = parse_optional_int(body.get("account_id"))

    reset_count = reset_completed_tasks_by_filters(
        session=session,
        status=status,
        task_type=task_type,
        account_id=account_id,
    )
    _, t = get_current_i18n()
    if reset_count > 0:
        message_template = t.get("msg_reset_completed_done") or "已重置 {count} 个任务"
        message = message_template.replace("{count}", str(reset_count))
    else:
        message = t.get("msg_reset_completed_empty") or "没有需要重置的任务"
    return _json({"ok": True, "count": reset_count, "message": message})


@router.get("/management/metadata")
async def get_management_metadata(
    selected_node_type: str = Query(default="root"),
    selected_node_id: str = Query(default="all"),
    selected_set_code: str = Query(default=""),
    selected_pack_name: str = Query(default=""),
    ui_step: int = Query(default=1),
    current_action: str = Query(default="update_new_series"),
    snapshot_id: str = Query(default=""),
):
    """获取元数据管理页面数据。"""
    return _json(
        build_metadata_context(
            ui_step=ui_step,
            selected_node_type=selected_node_type,
            selected_node_id=selected_node_id,
            selected_set_code=selected_set_code,
            selected_pack_name=selected_pack_name,
            snapshot_id=snapshot_id,
            current_action=current_action,
        )
    )


@router.post("/management/metadata/preview")
async def post_metadata_preview(request: Request):
    """生成元数据预览。"""
    body = await request.json()
    action = str(body.get("action") or "update_new_series")
    node_type = str(body.get("node_type") or "root")
    node_id = str(body.get("node_id") or "all")
    force_refresh = bool(body.get("force_refresh", False))

    result = preview_metadata_sync(
        node_type=node_type,
        node_id=node_id,
        action=action,
        force_refresh=force_refresh,
    )
    return _json(result)


@router.post("/management/metadata/execute")
async def post_metadata_execute(request: Request):
    """执行元数据同步。"""
    body = await request.json()
    snapshot_id = str(body.get("snapshot_id") or "")
    if not snapshot_id:
        raise HTTPException(status_code=400, detail="snapshot_id_required")
    result = execute_metadata_sync(snapshot_id)
    return _json(result)


@router.post("/management/metadata/check")
async def post_metadata_check():
    """检查元数据源状态。"""
    return _json(check_metadata_sources())


@router.get("/management/daily-gift")
async def get_management_daily_gift(
    biz_date_local: str | None = Query(default=None),
    account_id: str | None = Query(default=None),
    sort_by: str = Query(default="updated_at"),
    sort_order: str = Query(default="desc"),
    page: int = Query(default=0),
    page_size: int = Query(default=10),
    pair_page: int = Query(default=0),
    pair_page_size: int = Query(default=10),
    session: Session = Depends(get_fastapi_session),
):
    """获取每日送卡页面数据。"""
    return _json(
        build_daily_gift_context(
            session=session,
            biz_date_local=biz_date_local,
            account_id=parse_optional_int(account_id),
            sort_by=sort_by,
            sort_order=sort_order,
            page=max(page, 0),
            page_size=min(max(page_size, 1), 100),
            pair_page=max(pair_page, 0),
            pair_page_size=min(max(pair_page_size, 1), 100),
        )
    )


@router.get("/management/friendships")
async def get_management_friendships(
    account_id: str | None = Query(default=None),
    from_account_id: str | None = Query(default=None),
    q: str = Query(default=""),
    sort_by: str = Query(default="created_at"),
    sort_order: str = Query(default="desc"),
    page: int = Query(default=0),
    page_size: int = Query(default=10),
    session: Session = Depends(get_fastapi_session),
):
    """获取好友管理页面数据。"""
    context = build_friendship_context(
        session=session,
        account_id=parse_optional_int(account_id),
        from_account_id=parse_optional_int(from_account_id),
        q=q,
        sort_by=sort_by,
        sort_order=sort_order,
        page=max(page, 0),
        page_size=min(max(page_size, 1), 100),
    )
    return _json(context)


@router.post("/management/friendships/add")
async def post_friendship_add(
    request: Request,
    session: Session = Depends(get_fastapi_session),
):
    """创建添加好友请求。"""
    body = await request.json()
    from_account_id = parse_optional_int(body.get("from_account_id"))
    to_account_id = parse_optional_int(body.get("to_account_id"))
    to_friend_id = str(body.get("to_friend_id") or "").strip()

    if not to_friend_id and to_account_id:
        target_account = session.get(Account, to_account_id)
        if target_account and target_account.friend_id:
            to_friend_id = target_account.friend_id

    ok = bool(
        from_account_id
        and to_friend_id
        and create_add_request(
            from_account_id=from_account_id,
            to_friend_id=to_friend_id,
            to_account_id=to_account_id,
        )
    )
    _, t = get_current_i18n()
    return _json(
        {
            "ok": ok,
            "message": (
                t.get("msg_add_request_created")
                if ok
                else t.get("msg_add_request_skipped")
            )
            or ("添加请求已创建" if ok else "无效或重复请求，未创建添加申请"),
        }
    )


@router.post("/management/friendships/delete")
async def post_friendship_delete(
    request: Request,
    session: Session = Depends(get_fastapi_session),
):
    """创建删除好友请求。"""
    body = await request.json()
    from_account_id = parse_optional_int(body.get("from_account_id"))
    to_account_id = parse_optional_int(body.get("to_account_id"))
    friend_id = str(body.get("friend_id") or "").strip()

    if not friend_id and to_account_id:
        target_account = session.get(Account, to_account_id)
        if target_account and target_account.friend_id:
            friend_id = target_account.friend_id

    ok = bool(
        from_account_id
        and friend_id
        and create_delete_request(
            from_account_id=from_account_id,
            friend_id=friend_id,
            to_account_id=to_account_id,
        )
    )
    _, t = get_current_i18n()
    return _json(
        {
            "ok": ok,
            "message": (
                t.get("msg_delete_request_created")
                if ok
                else t.get("msg_delete_request_skipped_not_friend")
            )
            or ("删除请求已创建" if ok else "当前不是好友关系，无法创建删除请求"),
        }
    )


@router.post("/management/friendships/{request_id}/cancel")
async def post_friendship_cancel(request_id: int):
    """取消好友请求。"""
    ok = cancel_pending_request(request_id=request_id)
    _, t = get_current_i18n()
    return _json(
        {
            "ok": ok,
            "message": (
                t.get("msg_request_cancelled") if ok else t.get("msg_request_cancel_failed")
            )
            or ("请求记录已删除" if ok else "仅允许删除未执行的申请记录"),
        }
    )


@router.get("/management/exchange-cards")
async def get_management_exchange_cards(
    account_id: str | None = Query(default=None),
    status: str | None = Query(default=None),
    q: str = Query(default=""),
    sort_by: str = Query(default="created_at"),
    sort_order: str = Query(default="desc"),
    page: int = Query(default=0),
    page_size: int = Query(default=10),
    session: Session = Depends(get_fastapi_session),
):
    """获取交换卡页面数据。"""
    context = build_exchange_card_context(
        session=session,
        account_id=parse_optional_int(account_id),
        status=status or None,
        q=q,
        sort_by=sort_by,
        sort_order=sort_order,
        page=max(page, 0),
        page_size=min(max(page_size, 1), 100),
    )
    return _json(context)


@router.post("/management/exchange-cards/{request_id}/cancel")
async def post_exchange_cancel(request_id: int):
    """取消交换请求。"""
    ok = cancel_exchange_request(request_id=request_id)
    _, t = get_current_i18n()
    return _json(
        {
            "ok": ok,
            "message": (
                t.get("msg_exchange_request_cancelled")
                if ok
                else t.get("msg_exchange_request_cancel_failed")
            )
            or ("交换请求已取消" if ok else "交换请求取消失败"),
        }
    )


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
    parsed_is_read: bool | None = None
    if is_read == "true":
        parsed_is_read = True
    if is_read == "false":
        parsed_is_read = False

    context = build_notifications_context(
        session=session,
        scene=normalize_scene(scene) or None,
        account_id=parse_optional_int(account_id),
        is_read=parsed_is_read,
        q=q,
        sort_by=sort_by,
        sort_order=sort_order,
        page=max(page, 0),
        page_size=min(max(page_size, 1), 100),
    )
    return _json(context)


@router.post("/management/notifications/{notification_id}/mark-read")
async def post_mark_notification_read(notification_id: int):
    """标记通知已读。"""
    mark_notification_as_read(notification_id)
    return _json({"ok": True})


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
    return _json(
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
    return _json(
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
    selected_ids = _parse_unique_int_ids(request.query_params.getlist("notify_card_ids"))
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
    return _json(context)


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
    is_read_raw = str(body.get("is_read") or "").strip().lower()
    q = str(body.get("q") or "")
    sort_by = str(body.get("sort_by") or "created_at")
    sort_order = str(body.get("sort_order") or "desc")
    page = parse_optional_int(body.get("page")) or 0
    page_size = parse_optional_int(body.get("page_size")) or 10

    _, t = get_current_i18n()
    notification = None
    if notification_id is not None:
        notification = get_notification_by_id(notification_id)

    parsed_is_read: bool | None = None
    if is_read_raw == "true":
        parsed_is_read = True
    if is_read_raw == "false":
        parsed_is_read = False

    if notification is None:
        context = build_notifications_context(
            session=session,
            scene=scene,
            account_id=account_id,
            is_read=parsed_is_read,
            q=q,
            sort_by=sort_by,
            sort_order=sort_order,
            page=max(page, 0),
            page_size=min(max(page_size, 1), 100),
        )
        notifications = context.get("notifications") or []
        notification = notifications[0] if notifications else None

    if notification is None:
        return _json(
            {
                "ok": False,
                "message": t.get("webhook_test_empty") or "当前筛选下没有可测试通知",
            }
        )

    title = notification.title if hasattr(notification, "title") else notification.get("title", "")
    content = notification.content if hasattr(notification, "content") else notification.get("content", "")

    sent = get_notifier().send_webhook_notification(title=title, content=content)
    return _json(
        {
            "ok": sent,
            "message": (
                t.get("webhook_test_success") if sent else t.get("webhook_test_failed")
            )
            or ("测试消息已发送" if sent else "测试发送失败，请检查 Webhook URL"),
        }
    )
