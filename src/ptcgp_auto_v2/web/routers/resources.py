# -*- coding: utf-8 -*-
"""资源管理页路由。"""

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import HTMLResponse
from sqlmodel import Session

from ptcgp_auto_v2.db.engine import get_fastapi_session
from ptcgp_auto_v2.web.services.resource_service import build_resources_context
from ptcgp_auto_v2.web.utils.response_utils import render_template


router = APIRouter()


async def _render_management_resources(
    request: Request,
    session: Session,
    view: str = "stats",
    q: str = "",
    sort_by: str = "id",
    sort_order: str = "asc",
    page: int = 0,
    page_size: int = 10,
):
    """渲染资源管理列表。"""
    context = build_resources_context(
        session=session,
        view=view,
        q=q,
        sort_by=sort_by,
        sort_order=sort_order,
        page=page,
        page_size=page_size,
    )
    return render_template(request, "partials/resource_list.html", context)


@router.get("/management/resources", response_class=HTMLResponse)
async def get_management_resources(
    request: Request,
    view: str = Query(default="stats"),
    q: str = Query(default=""),
    sort_by: str = Query(default="id"),
    sort_order: str = Query(default="asc"),
    page: int = Query(default=0),
    page_size: int = Query(default=10),
    session: Session = Depends(get_fastapi_session),
):
    """渲染资源管理页。"""
    return await _render_management_resources(
        request=request,
        session=session,
        view=view,
        q=q,
        sort_by=sort_by,
        sort_order=sort_order,
        page=page,
        page_size=page_size,
    )
