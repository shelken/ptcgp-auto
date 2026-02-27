# -*- coding: utf-8 -*-
"""URL 构建工具函数。

提供统一的分页 URL 构建功能。
"""

from typing import Any
from urllib.parse import urlencode


def build_page_url(
    base_path: str,
    page: int,
    params: dict[str, Any] | None = None,
) -> str:
    """构建带分页参数的 URL。

    Args:
        base_path: URL 基础路径，如 "/api/tasks"
        page: 页码
        params: 其他查询参数字典

    Returns:
        完整的 URL 字符串
    """
    query_params = {**(params or {}), "page": page}
    # 过滤掉 None 值
    filtered_params = {
        k: v for k, v in query_params.items() if v is not None
    }
    if filtered_params:
        return f"{base_path}?{urlencode(filtered_params)}"
    return base_path


def build_tasks_page_url(
    page: int,
    lang: str,
    status: list[str],
    task_type: list[str],
    account_id: int | None,
    sort_by: str,
    sort_order: str,
) -> str:
    """构建任务分页 URL。

    Args:
        page: 页码
        lang: 语言
        status: 状态筛选列表
        task_type: 任务类型筛选列表
        account_id: 账号 ID
        sort_by: 排序字段
        sort_order: 排序方向

    Returns:
        完整的 URL 字符串
    """
    params: dict[str, Any] = {
        "lang": lang,
        "sort_by": sort_by,
        "sort_order": sort_order,
    }
    if account_id is not None:
        params["account_id"] = account_id

    query_parts = [f"page={page}"]
    for key, value in params.items():
        query_parts.append(f"{key}={value}")
    for s in status:
        if s:
            query_parts.append(f"status={s}")
    for t in task_type:
        if t:
            query_parts.append(f"task_type={t}")

    return f"/api/tasks?{'&'.join(query_parts)}"


def build_owned_cards_next_page_url(
    page: int,
    lang: str,
    sort_by: str,
    account_id: int | None,
    rarity: list[str],
    card_type: list[str],
    set_code: list[str],
    pack_name: list[str],
    element: list[str],
) -> str:
    """构建拥有卡牌分页 URL。

    Args:
        page: 页码
        lang: 语言
        sort_by: 排序字段
        account_id: 账号 ID
        rarity: 稀有度筛选列表
        card_type: 卡牌类型筛选列表
        set_code: 系列代码筛选列表
        pack_name: 卡包名称筛选列表
        element: 元素筛选列表

    Returns:
        完整的 URL 字符串
    """
    params: list[tuple[str, str]] = [
        ("page", str(page)),
        ("lang", lang),
        ("sort_by", sort_by),
    ]
    if account_id is not None:
        params.append(("account_id", str(account_id)))
    for r in rarity:
        if r:
            params.append(("rarity", r))
    for ct in card_type:
        if ct:
            params.append(("card_type", ct))
    for sc in set_code:
        if sc:
            params.append(("set_code", sc))
    for pn in pack_name:
        if pn:
            params.append(("pack_name", pn))
    for e in element:
        if e:
            params.append(("element", e))

    return f"/api/owned-cards?{urlencode(params)}"
