# -*- coding: utf-8 -*-
"""过滤与搜索工具函数。

提供统一的查询参数归一化和验证功能。
"""


def normalize_query_text(q: str | object | None) -> str:
    """归一化搜索词，兜底非字符串输入。

    Args:
        q: 原始搜索词，可以是字符串或其他类型

    Returns:
        归一化后的小写字符串
    """
    if isinstance(q, str):
        return q.strip().lower()
    return ""


def validate_sort_field(sort_by: str, allowed_fields: set[str], default: str) -> str:
    """验证排序字段是否在白名单中。

    Args:
        sort_by: 请求的排序字段
        allowed_fields: 允许的排序字段集合
        default: 默认排序字段

    Returns:
        验证后的排序字段
    """
    return sort_by if sort_by in allowed_fields else default


def normalize_sort_order(sort_order: str) -> str:
    """归一化排序方向为 asc 或 desc。

    Args:
        sort_order: 原始排序方向

    Returns:
        归一化后的排序方向
    """
    return "desc" if str(sort_order).lower() == "desc" else "asc"


def normalize_page(page: int) -> int:
    """归一化页码，确保非负。

    Args:
        page: 原始页码

    Returns:
        归一化后的页码
    """
    return max(page, 0)


def normalize_page_size(page_size: int, min_size: int = 1, max_size: int = 100) -> int:
    """归一化页面大小，确保在合理范围内。

    Args:
        page_size: 原始页面大小
        min_size: 最小页面大小，默认 1
        max_size: 最大页面大小，默认 100

    Returns:
        归一化后的页面大小
    """
    return min(max(page_size, min_size), max_size)
