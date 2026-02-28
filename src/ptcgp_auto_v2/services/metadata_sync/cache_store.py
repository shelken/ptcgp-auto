# -*- coding: utf-8 -*-
"""简单 TTL 缓存存储。"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any


class TTLCacheStore:
    """基于内存的 TTL 缓存。"""

    def __init__(self, ttl_seconds: int = 43200):
        self._ttl_seconds = ttl_seconds
        self._store: dict[str, tuple[datetime, Any]] = {}

    def get(self, key: str, now: datetime | None = None) -> Any | None:
        """获取缓存值。"""
        current_time = now or datetime.now()
        item = self._store.get(key)
        if item is None:
            return None
        expires_at, value = item
        if expires_at <= current_time:
            self._store.pop(key, None)
            return None
        return value

    def set(self, key: str, value: Any, ttl_seconds: int | None = None) -> None:
        """写入缓存值。"""
        ttl = ttl_seconds if ttl_seconds is not None else self._ttl_seconds
        expires_at = datetime.now() + timedelta(seconds=ttl)
        self._store[key] = (expires_at, value)

    def invalidate_prefix(self, prefix: str) -> int:
        """按前缀失效缓存键。"""
        keys = [key for key in self._store if key.startswith(prefix)]
        for key in keys:
            self._store.pop(key, None)
        return len(keys)
