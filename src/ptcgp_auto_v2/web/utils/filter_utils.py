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


def normalize_choice(
    value: str | None,
    *,
    allowed: set[str],
    default: str,
) -> str:
    """归一化枚举值，非法值回退默认值。"""
    normalized = str(value or "").strip()
    if normalized in allowed:
        return normalized
    return default


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
