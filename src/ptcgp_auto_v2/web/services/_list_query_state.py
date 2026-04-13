# -*- coding: utf-8 -*-
"""服务层列表查询状态工具。"""

from __future__ import annotations

from collections.abc import Container
from dataclasses import dataclass

from ptcgp_auto_v2.web.utils.filter_utils import (
    normalize_page,
    normalize_page_size,
    normalize_query_text,
    normalize_sort_order,
)


@dataclass(frozen=True)
class BasicListQueryState:
    """收敛服务层通用列表查询状态，减少页面级列表实现重复判断。"""

    raw_q: str
    normalized_q: str
    sort_by: str
    sort_order: str
    page: int
    page_size: int

    @property
    def has_prev(self) -> bool:
        """统一上一页判定，避免各列表重复推导。"""
        return self.page > 0

    def has_next(self, *, total: int) -> bool:
        """统一下一页判定，保持分页语义一致。"""
        return (self.page + 1) * self.page_size < total

    def page_bounds(self) -> tuple[int, int]:
        """统一页窗口边界，给内存分页场景复用。"""
        start = self.page * self.page_size
        return start, start + self.page_size

    def page_meta(self, *, total: int) -> dict[str, int | bool]:
        """统一列表分页回显字段。"""
        return {
            "page": self.page,
            "page_size": self.page_size,
            "has_prev": self.has_prev,
            "has_next": self.has_next(total=total),
            "total": total,
        }


def build_list_query_state(
    *,
    q: str = "",
    sort_by: str,
    sort_order: str,
    page: int,
    page_size: int,
    max_page_size: int = 100,
) -> BasicListQueryState:
    """构建基础列表查询状态。"""
    return BasicListQueryState(
        raw_q=q,
        normalized_q=normalize_query_text(q),
        sort_by=sort_by,
        sort_order=normalize_sort_order(sort_order),
        page=normalize_page(page),
        page_size=normalize_page_size(page_size, max_size=max_page_size),
    )


def build_sorted_list_query_state(
    *,
    q: str = "",
    sort_by: str,
    sort_order: str,
    page: int,
    page_size: int,
    allowed_sort_fields: Container[str],
    default_sort_by: str,
    max_page_size: int = 100,
) -> BasicListQueryState:
    """构建带排序字段 allowlist 的基础列表查询状态。"""
    normalized_sort_by = (
        sort_by if sort_by in allowed_sort_fields else default_sort_by
    )
    return build_list_query_state(
        q=q,
        sort_by=normalized_sort_by,
        sort_order=sort_order,
        page=page,
        page_size=page_size,
        max_page_size=max_page_size,
    )
