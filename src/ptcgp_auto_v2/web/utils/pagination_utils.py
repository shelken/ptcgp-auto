# -*- coding: utf-8 -*-
"""分页工具函数。

提供统一的分页参数验证和分页上下文构建功能。
"""

from typing import Any


def build_pagination_context(
    items: list[Any],
    page: int,
    page_size: int,
    total: int,
) -> dict[str, Any]:
    """构建统一的分页上下文。

    Args:
        items: 当前页数据列表
        page: 当前页码（从0开始）
        page_size: 页面大小
        total: 总数据量

    Returns:
        包含分页信息的上下文字典
    """
    start = page * page_size
    end = start + page_size
    return {
        "items": items,
        "page": page,
        "page_size": page_size,
        "has_prev": page > 0,
        "has_next": end < total,
        "total": total,
    }


def calc_page_bounds(page: int, page_size: int) -> tuple[int, int]:
    """计算分页的起始和结束位置。

    Args:
        page: 当前页码（从0开始）
        page_size: 页面大小

    Returns:
        (起始位置, 结束位置)
    """
    start = page * page_size
    end = start + page_size
    return start, end
