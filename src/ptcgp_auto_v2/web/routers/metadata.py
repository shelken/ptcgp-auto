import json

from fastapi import APIRouter, Request, Query
from fastapi.responses import HTMLResponse

from ptcgp_auto_v2.web.services.metadata_service import (
    build_metadata_context,
    update_set_label,
    update_pack_label,
    preview_metadata_sync,
    execute_metadata_sync,
    check_metadata_sources,
)
from ptcgp_auto_v2.web.utils.form_utils import safe_get_string
from ptcgp_auto_v2.web.utils.template_env import get_templates


router = APIRouter()


@router.get("/management/metadata", response_class=HTMLResponse)
async def get_management_metadata(
    request: Request,
    selected_node_type: str = Query(default="root"),
    selected_node_id: str = Query(default="all"),
    selected_set_code: str = Query(default=""),
    selected_pack_name: str = Query(default=""),
    ui_step: int = Query(default=1),
    current_action: str = Query(default="sync_supplement"),
):
    """渲染元数据管理页面。"""
    context = build_metadata_context(
        ui_step=ui_step,
        selected_node_type=selected_node_type,
        selected_node_id=selected_node_id,
        selected_set_code=selected_set_code,
        selected_pack_name=selected_pack_name,
    )
    context["current_action"] = current_action
    context["request"] = request
    templates = get_templates()
    return templates.TemplateResponse("partials/metadata_list.html", context)


@router.post("/api/metadata/set/{code}/label")
async def update_set_label_api(
    request: Request,
    code: str,
):
    """更新卡包系列中文名。"""
    form = await request.form()
    label_zh = safe_get_string(form, "label_zh") or ""
    update_set_label(code, label_zh)
    return await get_management_metadata(request)


@router.post("/api/metadata/pack/{name}/label")
async def update_pack_label_api(
    request: Request,
    name: str,
):
    """更新补充包中文名。"""
    form = await request.form()
    label_zh = safe_get_string(form, "label_zh") or ""
    update_pack_label(name, label_zh)
    return await get_management_metadata(request)


@router.post("/api/metadata/sync/preview")
async def preview_metadata_sync_api(
    request: Request,
):
    """生成元数据同步预览快照。"""
    form = await request.form()
    node_type = safe_get_string(form, "node_type") or "root"
    node_id = safe_get_string(form, "node_id") or "all"
    action = safe_get_string(form, "action") or "sync_supplement"
    selected_set_code = safe_get_string(form, "selected_set_code") or ""
    selected_pack_name = safe_get_string(form, "selected_pack_name") or ""
    current_action = safe_get_string(form, "current_action") or action
    ui_step_raw = safe_get_string(form, "ui_step") or "2"
    force_refresh = (safe_get_string(form, "force_refresh") or "0") == "1"
    try:
        ui_step = int(ui_step_raw)
    except ValueError:
        ui_step = 2

    try:
        result = preview_metadata_sync(
            node_type=node_type,
            node_id=node_id,
            action=action,
            force_refresh=force_refresh,
        )
    except ValueError as exc:
        return HTMLResponse(str(exc), status_code=400)

    preview_json = json.dumps(result, ensure_ascii=False)

    context = build_metadata_context(
        ui_step=ui_step,
        selected_node_type=node_type,
        selected_node_id=node_id,
        selected_set_code=selected_set_code,
        selected_pack_name=selected_pack_name,
    )
    context["current_action"] = current_action
    context["request"] = request
    context["sync_preview"] = result
    context["sync_preview_json"] = preview_json
    templates = get_templates()
    return templates.TemplateResponse("partials/metadata_list.html", context)


@router.post("/api/metadata/sync/execute")
async def execute_metadata_sync_api(
    request: Request,
):
    """执行已确认的元数据同步快照。"""
    form = await request.form()
    snapshot_id = safe_get_string(form, "snapshot_id") or ""
    node_type = safe_get_string(form, "node_type") or "root"
    node_id = safe_get_string(form, "node_id") or "all"
    selected_set_code = safe_get_string(form, "selected_set_code") or ""
    selected_pack_name = safe_get_string(form, "selected_pack_name") or ""
    current_action = safe_get_string(form, "current_action") or "sync_supplement"
    ui_step_raw = safe_get_string(form, "ui_step") or "3"
    try:
        ui_step = int(ui_step_raw)
    except ValueError:
        ui_step = 3

    try:
        result = execute_metadata_sync(snapshot_id)
    except ValueError as exc:
        return HTMLResponse(str(exc), status_code=400)

    context = build_metadata_context(
        ui_step=ui_step,
        selected_node_type=node_type,
        selected_node_id=node_id,
        selected_set_code=selected_set_code,
        selected_pack_name=selected_pack_name,
    )
    context["current_action"] = current_action
    context["request"] = request
    context["sync_execute_result"] = result
    context["sync_execute_result_json"] = json.dumps(result, ensure_ascii=False)
    templates = get_templates()
    return templates.TemplateResponse("partials/metadata_list.html", context)


@router.post("/api/metadata/sync/check")
async def check_metadata_sync_api(
    request: Request,
):
    """刷新元数据同步检查信息。"""
    form = await request.form()
    node_type = safe_get_string(form, "node_type") or "root"
    node_id = safe_get_string(form, "node_id") or "all"
    selected_set_code = safe_get_string(form, "selected_set_code") or ""
    selected_pack_name = safe_get_string(form, "selected_pack_name") or ""
    current_action = safe_get_string(form, "current_action") or "sync_supplement"
    ui_step_raw = safe_get_string(form, "ui_step") or "1"
    try:
        ui_step = int(ui_step_raw)
    except ValueError:
        ui_step = 1
    context = build_metadata_context(
        ui_step=ui_step,
        selected_node_type=node_type,
        selected_node_id=node_id,
        selected_set_code=selected_set_code,
        selected_pack_name=selected_pack_name,
    )
    context["current_action"] = current_action
    context["request"] = request
    context["sync_check"] = check_metadata_sources()
    templates = get_templates()
    return templates.TemplateResponse("partials/metadata_list.html", context)


@router.post("/api/metadata/node/select")
async def select_metadata_node_api(
    request: Request,
):
    """更新当前元数据层次节点选中态。"""
    form = await request.form()
    node_type = safe_get_string(form, "node_type") or "root"
    node_id = safe_get_string(form, "node_id") or "all"
    selected_set_code = safe_get_string(form, "selected_set_code") or ""
    selected_pack_name = safe_get_string(form, "selected_pack_name") or ""
    current_action = safe_get_string(form, "current_action") or "sync_supplement"
    ui_step_raw = safe_get_string(form, "ui_step") or "1"
    try:
        ui_step = int(ui_step_raw)
    except ValueError:
        ui_step = 1

    context = build_metadata_context(
        ui_step=ui_step,
        selected_node_type=node_type,
        selected_node_id=node_id,
        selected_set_code=selected_set_code,
        selected_pack_name=selected_pack_name,
    )
    context["current_action"] = current_action
    context["request"] = request
    templates = get_templates()
    return templates.TemplateResponse("partials/metadata_list.html", context)
