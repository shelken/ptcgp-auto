# -*- coding: utf-8 -*-
"""52poke 中文本地化同步服务。"""

from __future__ import annotations

import logging
import re
import time
from dataclasses import dataclass
from typing import Any
from urllib.parse import quote

import requests

from .cache_store import TTLCacheStore

# 创建 logger
logger = logging.getLogger(__name__)


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
        print(f"[52poke] API 请求: GET {url}", flush=True)
        start = time.time()
        response = requests.get(url, timeout=self.timeout)
        response.raise_for_status()
        elapsed = time.time() - start
        print(f"[52poke] API 响应: 入口页 - {elapsed:.2f}s", flush=True)
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
            f"&titles={quote(title)}&prop=revisions&rvslots=main&rvprop=content&converttitles=1"
        )
        print(f"[52poke] API 请求: GET {url}", flush=True)
        start = time.time()
        response = requests.get(url, timeout=self.timeout)
        response.raise_for_status()
        elapsed = time.time() - start
        print(f"[52poke] API 响应: {title} - {elapsed:.2f}s", flush=True)
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
        """按范围构建本地化映射。

        优化：先获取所有系列和卡包列表，根据 scope 过滤后再请求卡包页面，
        避免请求不需要的卡包页面。
        """
        cache_key = f"localized_map:{scope_level}:{scope_value or 'all'}"
        if not force_refresh:
            cached = self._cache.get(cache_key)
            if cached is not None:
                return cached

        entry_links = self._fetch_entry_links(force_refresh)
        all_series_titles = [
            title for title in entry_links if "系列" in title and "TCGP" in title
        ]

        results: dict[str, Any] = {"sets": [], "packs": [], "cards": []}
        target_set_code, target_number = self._parse_card_scope(
            scope_level, scope_value
        )

        # 根据 scope 过滤系列，减少不必要的请求
        series_titles = self._filter_series_by_scope(
            all_series_titles, scope_level, scope_value, target_set_code
        )

        # 第一阶段：获取所有系列和卡包列表（轻量级）
        all_packs: list[tuple[str, str]] = []  # (series_title, pack_title)
        for series_title in series_titles:
            series_wikitext = self._fetch_series_wikitext(series_title, force_refresh)
            pack_titles = self._parse_pack_titles_from_series(series_wikitext)
            for pack_title in pack_titles:
                # 如果指定了 pack scope，提前过滤
                if scope_level == "pack" and scope_value:
                    # 注意：pack_value 可能带或不带（TCGP）后缀
                    match = (
                        pack_title == scope_value
                        or pack_title == f"{scope_value}（TCGP）"
                        or f"{pack_title}（TCGP）" == scope_value
                    )
                    if not match:
                        continue
                all_packs.append((series_title, pack_title))

        # 第二阶段：按需获取卡包页面（重量级）
        # 优化：使用 pack_setcode_map 缓存避免请求不需要的卡包
        pack_setcode_map: dict[str, str] = self._cache.get("pack_setcode_map") or {}
        print(f"[52poke] pack_setcode_map 缓存: {len(pack_setcode_map)} 条", flush=True)

        # 如果已知 target_set_code，先用缓存映射过滤 pack 列表
        packs_to_fetch = all_packs
        if target_set_code and not force_refresh:
            filtered_packs = []
            for series_title, pack_title in all_packs:
                cached_set_code = pack_setcode_map.get(pack_title)
                if cached_set_code:
                    # 已知映射，直接过滤
                    if cached_set_code == target_set_code:
                        filtered_packs.append((series_title, pack_title))
                else:
                    # 未知映射，需要获取
                    filtered_packs.append((series_title, pack_title))
            packs_to_fetch = filtered_packs
            print(
                f"[52poke] 过滤后需获取: {len(packs_to_fetch)}/{len(all_packs)} 个 pack",
                flush=True,
            )

        print(f"[52poke] 开始并行获取 {len(packs_to_fetch)} 个卡包页面...", flush=True)

        def fetch_single_pack(item: tuple[str, str]) -> dict[str, Any] | None:
            """获取单个 pack 页面并解析。"""
            series_title, pack_title = item
            try:
                pack_wikitext = self._fetch_pack_wikitext(pack_title, force_refresh)
                set_code = self._parse_set_code(pack_wikitext)
                set_name = self._parse_set_name(pack_wikitext)

                # 缓存 pack -> set_code 映射
                if set_code:
                    pack_setcode_map[pack_title] = set_code

                if not set_code:
                    return None

                # 根据 set/card scope 过滤
                if scope_level == "set" and scope_value and set_code != scope_value:
                    return None
                if scope_level == "card" and set_code != target_set_code:
                    return None

                # 解析卡牌
                cards = []
                for number, localized_name in self._parse_card_rows(pack_wikitext):
                    if scope_level == "card" and number != target_number:
                        continue
                    cards.append(
                        {
                            "set_code": set_code,
                            "number": number,
                            "localized_name": localized_name,
                        }
                    )

                return {
                    "set_code": set_code,
                    "set_name": set_name,
                    "pack_title": pack_title,
                    "cards": cards,
                }
            except Exception as e:
                print(f"[52poke] 获取 pack 失败 {pack_title}: {e}", flush=True)
                return None

        # 并行获取所有 pack 页面
        from concurrent.futures import ThreadPoolExecutor, as_completed

        fetched_results = []
        with ThreadPoolExecutor(max_workers=10) as executor:
            future_to_pack = {
                executor.submit(fetch_single_pack, item): item
                for item in packs_to_fetch
            }
            for future in as_completed(future_to_pack):
                result = future.result()
                if result:
                    fetched_results.append(result)

        # 保存缓存
        self._cache.set("pack_setcode_map", pack_setcode_map)
        print(
            f"[52poke] 并行获取完成，命中 {len(fetched_results)}/{len(packs_to_fetch)} 个 pack",
            flush=True,
        )

        # 合并结果
        # 注意：52poke 的"卡包"对应 set，不是 pack，所以只更新 set 和 card
        for result in fetched_results:
            if result["set_name"]:
                results["sets"].append(
                    {"set_code": result["set_code"], "zh": result["set_name"]}
                )
            results["cards"].extend(result["cards"])

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
        """读取卡包页 wikitext（带缓存）。

        注意：从系列页解析出的标题不含（TCGP）后缀，
        但实际页面标题需要加上（TCGP）。
        """
        # 确保标题包含（TCGP）后缀
        full_title = title if "（TCGP）" in title else f"{title}（TCGP）"
        key = f"pack_wikitext:{full_title}"
        if not force_refresh:
            cached = self._cache.get(key)
            if cached is not None:
                return str(cached)
        value = self._client.fetch_pack_wikitext(full_title)
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

    def _filter_series_by_scope(
        self,
        all_series: list[str],
        scope_level: str,
        scope_value: str | None,
        target_set_code: str | None,
    ) -> list[str]:
        """根据 scope 过滤需要获取的系列。

        例如：set=A1 只需要 A 系列，不需要 B 系列。
        """
        if scope_level == "all" or not scope_value:
            return all_series

        # set/card scope：根据 set_code 前缀判断系列
        if target_set_code:
            prefix = target_set_code[0].upper() if target_set_code else None
            if prefix:
                return [t for t in all_series if f"{prefix}系列" in t]

        # pack scope：需要获取所有系列来查找（暂时无法根据 pack 名定位系列）
        return all_series

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
