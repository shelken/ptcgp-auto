# -*- coding: utf-8 -*-
"""资源页服务层。"""

from __future__ import annotations

from typing import Any

from sqlmodel import Session

from ptcgp_auto_v2.web.services._list_query_state import build_list_query_state
from ptcgp_auto_v2.web.queries.resource_queries import (
    list_account_resources,
    list_pack_point_resources,
)


DEFAULT_RESOURCE_VIEW = "stats"
"""资源页默认视图。"""

PACK_POINTS_VIEW = "pack-points"
"""资源页包点数视图标识。"""

STATS_SORT_FIELDS = {
    "id",
    "nickname",
    "friend_id",
    "exchange_points",
    "pack_hourglass_count",
    "updated_at",
}
"""stats 视图允许的排序字段。"""

PACK_POINTS_BASE_SORT_FIELDS = {"id", "nickname", "friend_id"}
"""pack-points 视图允许的基础排序字段。"""


def _normalize_resource_view(view: str) -> str:
    """归一化资源页视图。"""
    return (
        view
        if view in {DEFAULT_RESOURCE_VIEW, PACK_POINTS_VIEW}
        else DEFAULT_RESOURCE_VIEW
    )


def _is_pack_points_sort_field(sort_by: str) -> bool:
    """判断是否为 pack-points 视图允许的排序字段。"""
    if sort_by in PACK_POINTS_BASE_SORT_FIELDS:
        return True
    if not sort_by.startswith("series:"):
        return False
    return bool(sort_by.split(":", 1)[1].strip())


def _normalize_sort_by_for_view(view: str, sort_by: str) -> str:
    """按当前视图归一化排序字段。"""
    if view == PACK_POINTS_VIEW:
        return sort_by if _is_pack_points_sort_field(sort_by) else "id"
    return sort_by if sort_by in STATS_SORT_FIELDS else "id"


def build_resources_context(
    *,
    session: Session,
    view: str = DEFAULT_RESOURCE_VIEW,
    q: str = "",
    sort_by: str = "id",
    sort_order: str = "asc",
    page: int = 0,
    page_size: int = 20,
) -> dict[str, Any]:
    """构建资源页上下文。"""
    normalized_view = _normalize_resource_view(view)
    normalized_sort_by = _normalize_sort_by_for_view(normalized_view, sort_by)
    list_state = build_list_query_state(
        q=q,
        sort_by=normalized_sort_by,
        sort_order=sort_order,
        page=page,
        page_size=page_size,
    )

    if normalized_view == PACK_POINTS_VIEW:
        result = list_pack_point_resources(
            session=session,
            q=list_state.raw_q,
            sort_by=list_state.sort_by,
            sort_order=list_state.sort_order,
            page=list_state.page,
            page_size=list_state.page_size,
        )
        items = result["rows"]
        total = result["total"]
        series_list = result["series_list"]
    else:
        items, total = list_account_resources(
            session=session,
            q=list_state.raw_q,
            sort_by=list_state.sort_by,
            sort_order=list_state.sort_order,
            page=list_state.page,
            page_size=list_state.page_size,
        )
        series_list = []

    return {
        "view": normalized_view,
        "items": items,
        "q": q,
        "sort_by": list_state.sort_by,
        "sort_order": list_state.sort_order,
        **list_state.page_meta(total=total),
        "series_list": series_list,
    }
