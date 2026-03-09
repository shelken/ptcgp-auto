import json

from fastapi import APIRouter, Request, Query
from fastapi.responses import HTMLResponse

from ptcgp_auto_v2.web.services.metadata_service import (
    build_metadata_context,
    preview_metadata_sync,
    execute_metadata_sync,
    check_metadata_sources,
)
from ptcgp_auto_v2.web.utils.form_utils import safe_get_string
from ptcgp_auto_v2.web.utils.response_utils import render_template


router = APIRouter()


def _parse_ui_step(raw_value: str, default_step: int) -> int:
    """解析表单中的 ui_step，非法值回退到默认值。"""
    try:
        return int(raw_value)
    except ValueError:
        return default_step


def _parse_metadata_form_state(form, *, default_step: int, default_action: str) -> dict[str, str | int]:
    """统一解析元数据管理页面公共表单字段。"""
    return {
        "node_type": safe_get_string(form, "node_type") or "root",
        "node_id": safe_get_string(form, "node_id") or "all",
        "selected_set_code": safe_get_string(form, "selected_set_code") or "",
        "selected_pack_name": safe_get_string(form, "selected_pack_name") or "",
        "current_action": safe_get_string(form, "current_action") or default_action,
        "snapshot_id": safe_get_string(form, "snapshot_id") or "",
        "ui_step": _parse_ui_step(safe_get_string(form, "ui_step") or str(default_step), default_step),
    }


@router.get("/management/metadata", response_class=HTMLResponse)
async def get_management_metadata(
    request: Request,
    selected_node_type: str = Query(default="root"),
    selected_node_id: str = Query(default="all"),
    selected_set_code: str = Query(default=""),
    selected_pack_name: str = Query(default=""),
    ui_step: int = Query(default=1),
    current_action: str = Query(default="update_new_series"),
    snapshot_id: str = Query(default=""),
):
    """渲染元数据管理页面。"""
    context = build_metadata_context(
        ui_step=ui_step,
        selected_node_type=selected_node_type,
        selected_node_id=selected_node_id,
        selected_set_code=selected_set_code,
        selected_pack_name=selected_pack_name,
        snapshot_id=snapshot_id,
        current_action=current_action,
    )
    return render_template(request, "partials/metadata_list.html", context)


@router.post("/api/metadata/sync/preview")
async def preview_metadata_sync_api(
    request: Request,
):
    """生成元数据同步预览快照。"""
    form = await request.form()
    action = safe_get_string(form, "action") or "update_new_series"
    form_state = _parse_metadata_form_state(form, default_step=2, default_action=action)
    force_refresh = (safe_get_string(form, "force_refresh") or "0") == "1"

    try:
        result = preview_metadata_sync(
            node_type=form_state["node_type"],
            node_id=form_state["node_id"],
            action=action,
            force_refresh=force_refresh,
        )
    except ValueError as exc:
        return HTMLResponse(str(exc), status_code=400)

    preview_json = json.dumps(result, ensure_ascii=False)

    context = build_metadata_context(
        ui_step=form_state["ui_step"],
        selected_node_type=form_state["node_type"],
        selected_node_id=form_state["node_id"],
        selected_set_code=form_state["selected_set_code"],
        selected_pack_name=form_state["selected_pack_name"],
        snapshot_id=result.get("snapshot_id") or form_state["snapshot_id"],
        current_action=form_state["current_action"],
    )
    context["sync_preview"] = result
    context["sync_preview_json"] = preview_json
    return render_template(request, "partials/metadata_list.html", context)


@router.post("/api/metadata/sync/execute")
async def execute_metadata_sync_api(
    request: Request,
):
    """执行已确认的元数据同步快照。"""
    form = await request.form()
    form_state = _parse_metadata_form_state(form, default_step=1, default_action="update_new_series")
    snapshot_id = form_state["snapshot_id"]

    try:
        result = execute_metadata_sync(snapshot_id)
    except ValueError as exc:
        return HTMLResponse(str(exc), status_code=400)

    context = build_metadata_context(
        ui_step=1,
        selected_node_type=form_state["node_type"],
        selected_node_id=form_state["node_id"],
        selected_set_code=form_state["selected_set_code"],
        selected_pack_name=form_state["selected_pack_name"],
        snapshot_id=snapshot_id,
        current_action=form_state["current_action"],
    )
    context["sync_execute_result"] = result
    context["sync_execute_result_json"] = json.dumps(result, ensure_ascii=False)
    return render_template(request, "partials/metadata_list.html", context)


@router.post("/api/metadata/sync/check")
async def check_metadata_sync_api(
    request: Request,
):
    """刷新元数据同步检查信息。"""
    form = await request.form()
    form_state = _parse_metadata_form_state(form, default_step=1, default_action="update_new_series")
    context = build_metadata_context(
        ui_step=form_state["ui_step"],
        selected_node_type=form_state["node_type"],
        selected_node_id=form_state["node_id"],
        selected_set_code=form_state["selected_set_code"],
        selected_pack_name=form_state["selected_pack_name"],
        snapshot_id=form_state["snapshot_id"],
        current_action=form_state["current_action"],
    )
    context["sync_check"] = check_metadata_sources()
    return render_template(request, "partials/metadata_list.html", context)


@router.post("/api/metadata/node/select")
async def select_metadata_node_api(
    request: Request,
):
    """更新当前元数据层次节点选中态。"""
    form = await request.form()
    form_state = _parse_metadata_form_state(form, default_step=1, default_action="update_new_series")

    context = build_metadata_context(
        ui_step=form_state["ui_step"],
        selected_node_type=form_state["node_type"],
        selected_node_id=form_state["node_id"],
        selected_set_code=form_state["selected_set_code"],
        selected_pack_name=form_state["selected_pack_name"],
        snapshot_id=form_state["snapshot_id"],
        current_action=form_state["current_action"],
    )
    return render_template(request, "partials/metadata_list.html", context)
