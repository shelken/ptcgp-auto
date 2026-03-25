# -*- coding: utf-8 -*-
"""React API 路由公共工具。"""

from __future__ import annotations

from typing import Any

from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse

from ptcgp_auto_v2.web.utils.filter_utils import normalize_page, normalize_page_size


def json_response(payload: Any) -> JSONResponse:
    """统一 JSON 输出。"""
    return JSONResponse(content=jsonable_encoder(payload))


def parse_unique_int_ids(values: list[str]) -> list[int]:
    """解析并去重整数 ID 列表，保留原顺序。"""
    parsed_ids: list[int] = []
    for item in values:
        if not str(item).isdigit():
            continue
        parsed = int(item)
        if parsed not in parsed_ids:
            parsed_ids.append(parsed)
    return parsed_ids


def parse_bool_flag(raw: str | None) -> bool | None:
    """解析 true/false 字符串为布尔值。"""
    normalized = str(raw or "").strip().lower()
    if normalized == "true":
        return True
    if normalized == "false":
        return False
    return None


def normalize_pagination_params(
    *,
    page: int,
    page_size: int,
    max_size: int = 100,
) -> tuple[int, int]:
    """统一归一化分页参数。"""
    return normalize_page(page), normalize_page_size(page_size, max_size=max_size)
