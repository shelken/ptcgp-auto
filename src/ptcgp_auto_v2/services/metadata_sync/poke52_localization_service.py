# -*- coding: utf-8 -*-
"""52poke 中文本地化同步服务。"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any
from urllib.parse import quote

import requests

from .cache_store import TTLCacheStore


@dataclass
class _MediaWikiClient:
    """MediaWiki API 访问客户端。"""

    timeout: int = 30

    def fetch_entry_links(self) -> list[str]:
        """获取 TCGP 入口页链接标题。"""
        url = (
            "https://wiki.52poke.com/api.php?action=query&format=json&formatversion=2"
            "&titles=Pok%C3%A9mon_Trading_Card_Game_Pocket&prop=links&pllimit=max"
        )
        response = requests.get(url, timeout=self.timeout)
        response.raise_for_status()
        data = response.json()
        links = ((data.get("query") or {}).get("pages") or [{}])[0].get("links") or []
        return [str(item.get("title")) for item in links if item.get("title")]

    def fetch_series_wikitext(self, title: str) -> str:
        """获取系列页 wikitext。"""
        return self._fetch_page_wikitext(title)

    def fetch_pack_wikitext(self, title: str) -> str:
        """获取卡包页 wikitext。"""
        return self._fetch_page_wikitext(title)

    def _fetch_page_wikitext(self, title: str) -> str:
        """按标题获取页面 wikitext。"""
        url = (
            "https://wiki.52poke.com/api.php?action=query&format=json&formatversion=2"
            f"&titles={quote(title)}&prop=revisions&rvslots=main&rvprop=content"
        )
        response = requests.get(url, timeout=self.timeout)
        response.raise_for_status()
        data = response.json()
        pages = (data.get("query") or {}).get("pages") or []
        if not pages:
            return ""
        revisions = pages[0].get("revisions") or []
        if not revisions:
            return ""
        return str(revisions[0].get("slots", {}).get("main", {}).get("content", ""))


class Poke52LocalizationService:
    """52poke 中文本地化抓取与缓存服务。"""

    def __init__(
        self,
        client: Any | None = None,
        cache: TTLCacheStore | None = None,
    ) -> None:
        self._client = client or _MediaWikiClient()
        self._cache = cache or TTLCacheStore(ttl_seconds=43200)

    def build_localization_map(
        self,
        scope_level: str,
        scope_value: str | None,
        force_refresh: bool = False,
    ) -> dict[str, Any]:
        """按范围构建本地化映射。"""
        cache_key = f"localized_map:{scope_level}:{scope_value or 'all'}"
        if not force_refresh:
            cached = self._cache.get(cache_key)
            if cached is not None:
                return cached

        entry_links = self._fetch_entry_links(force_refresh)
        series_titles = [
            title for title in entry_links if "系列" in title and "TCGP" in title
        ]

        results: dict[str, Any] = {"sets": [], "packs": [], "cards": []}
        target_set_code, target_number = self._parse_card_scope(
            scope_level, scope_value
        )

        for series_title in series_titles:
            series_wikitext = self._fetch_series_wikitext(series_title, force_refresh)
            pack_titles = self._parse_pack_titles_from_series(series_wikitext)
            for pack_title in pack_titles:
                if scope_level == "pack" and scope_value and pack_title != scope_value:
                    continue
                pack_wikitext = self._fetch_pack_wikitext(pack_title, force_refresh)
                set_code = self._parse_set_code(pack_wikitext)
                set_name = self._parse_set_name(pack_wikitext)
                if not set_code:
                    continue

                if scope_level == "set" and scope_value and set_code != scope_value:
                    continue

                if set_name:
                    results["sets"].append({"set_code": set_code, "zh": set_name})
                    results["packs"].append(
                        {
                            "set_code": set_code,
                            "pack_name": pack_title,
                            "zh": set_name,
                        }
                    )

                for number, localized_name in self._parse_card_rows(pack_wikitext):
                    if scope_level == "card":
                        if set_code != target_set_code or number != target_number:
                            continue
                    results["cards"].append(
                        {
                            "set_code": set_code,
                            "number": number,
                            "localized_name": localized_name,
                        }
                    )

        results["sets"] = self._dedupe_rows(results["sets"], ["set_code"])
        results["packs"] = self._dedupe_rows(
            results["packs"], ["set_code", "pack_name"]
        )
        results["cards"] = self._dedupe_rows(results["cards"], ["set_code", "number"])

        self._cache.set(cache_key, results)
        return results

    def fetch_remote_stats(self) -> dict[str, int]:
        """获取 52poke 远端基础统计。"""
        try:
            entry_links = self._fetch_entry_links(force_refresh=False)
            series_titles = [
                title for title in entry_links if "系列" in title and "TCGP" in title
            ]
            pack_count = 0
            for title in series_titles:
                text = self._fetch_series_wikitext(title, force_refresh=False)
                pack_count += len(self._parse_pack_titles_from_series(text))
            return {
                "series": len(series_titles),
                "packs": pack_count,
            }
        except Exception as exc:  # pragma: no cover - 网络异常分支
            raise RuntimeError(f"拉取 52poke 统计失败: {exc}") from exc

    def _fetch_entry_links(self, force_refresh: bool) -> list[str]:
        """读取入口页链接（带缓存）。"""
        key = "entry_links"
        if not force_refresh:
            cached = self._cache.get(key)
            if cached is not None:
                return cached
        value = self._client.fetch_entry_links()
        self._cache.set(key, value)
        return value

    def _fetch_series_wikitext(self, title: str, force_refresh: bool) -> str:
        """读取系列页 wikitext（带缓存）。"""
        key = f"series_wikitext:{title}"
        if not force_refresh:
            cached = self._cache.get(key)
            if cached is not None:
                return str(cached)
        value = self._client.fetch_series_wikitext(title)
        self._cache.set(key, value)
        return value

    def _fetch_pack_wikitext(self, title: str, force_refresh: bool) -> str:
        """读取卡包页 wikitext（带缓存）。"""
        key = f"pack_wikitext:{title}"
        if not force_refresh:
            cached = self._cache.get(key)
            if cached is not None:
                return str(cached)
        value = self._client.fetch_pack_wikitext(title)
        self._cache.set(key, value)
        return value

    def _parse_pack_titles_from_series(self, text: str) -> list[str]:
        """从系列页解析卡包标题列表。"""
        return re.findall(r"\*\s*\{\{TCGP\|([^\}]+)\}\}", text)

    def _parse_set_code(self, text: str) -> str | None:
        """从卡包页解析 set_code。"""
        match = re.search(r"\|alt\s*=\s*([^\n\r]+)", text)
        if not match:
            return None
        return match.group(1).strip()

    def _parse_set_name(self, text: str) -> str | None:
        """从卡包页解析中文系列名。"""
        match = re.search(r"\|setname\s*=\s*([^\n\r]+)", text)
        if not match:
            return None
        return match.group(1).strip()

    def _parse_card_rows(self, text: str) -> list[tuple[int, str]]:
        """从卡包页解析卡牌编号与中文名。"""
        rows: list[tuple[int, str]] = []
        for number_str, body in re.findall(
            r"\{\{卡牌列表/entryp\|([^\|]+)\|([^\}]*)\}\}", text
        ):
            number = self._parse_number(number_str)
            if number is None:
                continue
            name = self._extract_name(body)
            if not name:
                continue
            rows.append((number, name))
        return rows

    def _extract_name(self, body: str) -> str | None:
        """提取中文卡牌名。"""
        m_c = re.search(r"\{\{C\|([^\|\}]+)", body)
        if m_c:
            return m_c.group(1).strip()
        m_t = re.search(r"\{\{TCGP\|([^\|\}]+)", body)
        if m_t:
            return m_t.group(1).strip()
        return None

    def _parse_number(self, text: str) -> int | None:
        """解析编号文本，如 001/286。"""
        m = re.search(r"(\d{1,3})", text)
        if not m:
            return None
        return int(m.group(1))

    def _parse_card_scope(
        self, scope_level: str, scope_value: str | None
    ) -> tuple[str | None, int | None]:
        """解析 card 范围参数。"""
        if scope_level != "card" or not scope_value:
            return None, None
        if "-" not in scope_value:
            raise ValueError("card 范围必须为 set-number，例如 A1-001")
        set_code, raw_num = scope_value.split("-", 1)
        number = self._parse_number(raw_num)
        if number is None:
            raise ValueError(f"无法解析卡牌编号: {scope_value}")
        return set_code, number

    def _dedupe_rows(
        self, rows: list[dict[str, Any]], keys: list[str]
    ) -> list[dict[str, Any]]:
        """按键去重并保持顺序。"""
        seen: set[tuple[Any, ...]] = set()
        result: list[dict[str, Any]] = []
        for row in rows:
            k = tuple(row.get(name) for name in keys)
            if k in seen:
                continue
            seen.add(k)
            result.append(row)
        return result
