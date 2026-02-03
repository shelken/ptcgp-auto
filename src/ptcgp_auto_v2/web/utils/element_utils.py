# -*- coding: utf-8 -*-

from typing import Iterable, List


def normalize_elements(elements: Iterable[str | None]) -> List[str]:
    """归一化属性列表，统一小写并去重。"""
    normalized = []
    seen = set()
    for item in elements:
        if not item:
            continue
        value = str(item).strip().lower()
        if not value:
            continue
        if value in seen:
            continue
        seen.add(value)
        normalized.append(value)
    return sorted(normalized)
