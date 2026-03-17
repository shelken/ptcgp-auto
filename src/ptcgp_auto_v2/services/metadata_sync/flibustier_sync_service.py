# -*- coding: utf-8 -*-
"""flibustier 元数据同步服务。"""

from __future__ import annotations

import copy
import json
from typing import Any

import requests

from ptcgp_auto_v2.db.models import Card, CardSet, Pack
from ptcgp_auto_v2.db.repositories import CardRepository
from ptcgp_auto_v2.services.metadata_sync.cache_store import TTLCacheStore

BASE_URL = (
    "https://raw.githubusercontent.com/flibustier/pokemon-tcg-pocket-database/main/dist"
)
SETS_URL = f"{BASE_URL}/sets.json"
CARDS_URL = f"{BASE_URL}/cards.json"
CARDS_EXTRA_URL = f"{BASE_URL}/cards.extra.json"


class FlibustierSyncService:
    """负责构建 flibustier 同步预览计划并执行。"""

    def __init__(
        self,
        repo: CardRepository,
        cache: TTLCacheStore | None = None,
        cache_ttl_seconds: int = 21600,
    ):
        self._repo = repo
        self._cache = cache
        self._cache_ttl_seconds = cache_ttl_seconds

    def build_plan(
        self,
        mode: str,
        scope_level: str,
        scope_value: str | None,
        sets_data: dict[str, list[dict[str, Any]]],
        cards_data: list[dict[str, Any]],
        extra_map: dict[tuple[str, int], dict[str, Any]],
    ) -> dict[str, Any]:
        """构建可执行计划（不落库）。"""
        if mode not in {"supplement", "force"}:
            raise ValueError(f"不支持的同步模式: {mode}")
        if scope_level not in {"all", "set", "pack", "card"}:
            raise ValueError(f"不支持的同步范围: {scope_level}")

        all_sets = self._flatten_sets(sets_data)
        filtered_sets, filtered_cards = self._filter_scope(
            scope_level=scope_level,
            scope_value=scope_value,
            all_sets=all_sets,
            all_cards=cards_data,
        )

        operations: dict[str, Any] = {"sets": [], "packs": [], "cards": []}

        # card / pack 级同步只关注目标对象，避免把系列更新混入预览结果。
        include_set_operations = scope_level in {"all", "set"}
        if include_set_operations:
            for set_item in filtered_sets:
                op = self._build_set_operation(set_item, mode)
                if op is not None:
                    operations["sets"].append(op)

        detected_packs: dict[str, str] = {}
        for card_item in filtered_cards:
            card_op = self._build_card_operation(card_item, extra_map, mode)
            if card_op is None:
                continue
            operations["cards"].append(card_op)
            for pack_name in card_op["add_pack_names"]:
                detected_packs[pack_name] = card_op["card"]["set_code"]

        for pack_name, set_code in detected_packs.items():
            pack_op = self._build_pack_operation(pack_name, set_code, mode)
            if pack_op is not None:
                operations["packs"].append(pack_op)

        summary = {
            "upsert_sets": len(operations["sets"]),
            "upsert_packs": len(operations["packs"]),
            "card_updates": sum(
                1 for item in operations["cards"] if item["needs_upsert"]
            ),
            "card_pack_links_to_add": sum(
                len(item["add_pack_names"]) for item in operations["cards"]
            ),
            "card_pack_links_to_remove": 0,
        }
        return {
            "mode": mode,
            "scope_level": scope_level,
            "scope_value": scope_value,
            "summary": summary,
            "operations": operations,
        }

    def fetch_remote_metadata(
        self,
        force_refresh: bool = False,
    ) -> tuple[
        dict[str, list[dict[str, Any]]],
        list[dict[str, Any]],
        dict[tuple[str, int], dict[str, Any]],
    ]:
        """抓取 flibustier 远端元数据。"""
        cache_key = "flibustier:remote_metadata"
        if self._cache and not force_refresh:
            cached = self._cache.get(cache_key)
            if cached is not None:
                sets_data, cards_data, extra_map = cached
                return (
                    copy.deepcopy(sets_data),
                    copy.deepcopy(cards_data),
                    copy.deepcopy(extra_map),
                )

        try:
            sets_response = requests.get(SETS_URL, timeout=30)
            sets_response.raise_for_status()
            sets_data = sets_response.json()

            cards_response = requests.get(CARDS_URL, timeout=60)
            cards_response.raise_for_status()
            cards_data = cards_response.json()

            extra_response = requests.get(CARDS_EXTRA_URL, timeout=60)
            extra_response.raise_for_status()
            extra_data = extra_response.json()
        except Exception as exc:  # pragma: no cover - 网络异常分支
            raise RuntimeError(f"拉取 flibustier 元数据失败: {exc}") from exc

        extra_map: dict[tuple[str, int], dict[str, Any]] = {}
        for item in extra_data:
            set_code = item.get("set")
            number = self._normalize_number(item.get("number"))
            if set_code and number is not None:
                extra_map[(str(set_code), number)] = item

        if self._cache:
            self._cache.set(
                cache_key,
                (
                    copy.deepcopy(sets_data),
                    copy.deepcopy(cards_data),
                    copy.deepcopy(extra_map),
                ),
                ttl_seconds=self._cache_ttl_seconds,
            )

        return sets_data, cards_data, extra_map

    def fetch_remote_stats(self, force_refresh: bool = False) -> dict[str, int]:
        """抓取远端基础统计。"""
        sets_data, cards_data, _ = self.fetch_remote_metadata(
            force_refresh=force_refresh
        )
        set_count = sum(len(items) for items in sets_data.values())
        return {
            "sets": set_count,
            "cards": len(cards_data),
        }

    def execute_plan(self, operations: dict[str, Any]) -> dict[str, int]:
        """执行同步计划。"""
        set_count = 0
        card_count = 0
        pack_count = 0
        link_count = 0

        for set_data in operations.get("sets", []):
            self._repo.upsert_set(CardSet.model_validate(set_data))
            set_count += 1

        for card_item in operations.get("cards", []):
            card_model = Card.model_validate(card_item["card"])
            card_id: int | None = card_item.get("existing_card_id")
            if card_item.get("needs_upsert"):
                saved_card = self._repo.upsert_card(card_model)
                card_id = saved_card.id
                card_count += 1

            if card_id is None:
                continue
            for pack_name in card_item.get("add_pack_names", []):
                self._repo.add_card_pack(card_id, pack_name)
                link_count += 1

        for pack_data in operations.get("packs", []):
            self._repo.upsert_pack_safe(Pack.model_validate(pack_data))
            pack_count += 1

        return {
            "upsert_sets": set_count,
            "upsert_packs": pack_count,
            "card_updates": card_count,
            "card_pack_links_to_add": link_count,
            "card_pack_links_to_remove": 0,
        }

    def _flatten_sets(
        self, sets_data: dict[str, list[dict[str, Any]]]
    ) -> list[dict[str, Any]]:
        """将 sets.json 结构扁平化。"""
        result: list[dict[str, Any]] = []
        for items in sets_data.values():
            result.extend(items)
        return result

    def _filter_scope(
        self,
        scope_level: str,
        scope_value: str | None,
        all_sets: list[dict[str, Any]],
        all_cards: list[dict[str, Any]],
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        """按范围过滤集合与卡牌。"""
        if scope_level == "all" or not scope_value:
            return all_sets, all_cards

        if scope_level == "set":
            set_code = scope_value
            return (
                [item for item in all_sets if str(item.get("code")) == set_code],
                [item for item in all_cards if str(item.get("set")) == set_code],
            )

        if scope_level == "pack":
            pack_name = scope_value
            cards = [
                item
                for item in all_cards
                if pack_name in [str(name) for name in item.get("packs", [])]
            ]
            set_codes = {str(item.get("set")) for item in cards}
            sets = [item for item in all_sets if str(item.get("code")) in set_codes]
            return sets, cards

        # card 范围: 格式 set_code-number，例如 A1-001
        set_code, number = self._parse_card_scope(scope_value)
        cards = [
            item
            for item in all_cards
            if str(item.get("set")) == set_code
            and self._normalize_number(item.get("number")) == number
        ]
        sets = [item for item in all_sets if str(item.get("code")) == set_code]
        return sets, cards

    def _parse_card_scope(self, scope_value: str) -> tuple[str, int]:
        """解析 card 范围参数。"""
        if "-" not in scope_value:
            raise ValueError("card 范围必须为 set-number，例如 A1-001")
        set_code, raw_number = scope_value.split("-", 1)
        number = self._normalize_number(raw_number)
        if number is None:
            raise ValueError(f"无法解析卡牌编号: {scope_value}")
        return set_code, number

    def _build_set_operation(
        self, set_item: dict[str, Any], mode: str
    ) -> dict[str, Any] | None:
        """构建系列写入动作。"""
        code = str(set_item.get("code") or "")
        if not code:
            return None
        existing_set = self._repo.get_set_by_code(code)
        print(f"[flibustier] set code={code}, existing={existing_set is not None}", flush=True)
        if mode == "supplement" and existing_set is not None:
            print("[flibustier] supplement mode, set exists, skip", flush=True)
            return None

        incoming_name = set_item.get("name", {})
        label_dict: dict[str, Any] = {}
        if existing_set and existing_set.label_data:
            try:
                data = json.loads(existing_set.label_data)
                if isinstance(data, dict):
                    label_dict = data
            except (TypeError, ValueError):
                label_dict = {}

        if isinstance(incoming_name, dict):
            label_dict.update(incoming_name)
            set_name = str(incoming_name.get("en") or incoming_name.get("zh") or code)
        else:
            set_name = str(incoming_name)
            label_dict.setdefault("en", set_name)

        # 计算字段变化
        changed_values: list[dict[str, str]] = []
        new_release_date = set_item.get("releaseDate")
        new_total_cards = int(set_item.get("count") or 0)
        new_label_data = json.dumps(label_dict, ensure_ascii=False)

        if existing_set is None:
            # 新增：记录所有字段的新值
            changed_values.append({"field": "name", "from": "", "to": set_name})
            if new_release_date:
                changed_values.append({"field": "release_date", "from": "", "to": str(new_release_date)})
            if new_total_cards:
                changed_values.append({"field": "total_cards", "from": "0", "to": str(new_total_cards)})
        else:
            # 更新：对比变化
            if existing_set.name != set_name:
                changed_values.append({"field": "name", "from": existing_set.name or "", "to": set_name})
            if str(existing_set.release_date or "") != str(new_release_date or ""):
                changed_values.append({"field": "release_date", "from": str(existing_set.release_date or ""), "to": str(new_release_date or "")})
            if (existing_set.total_cards or 0) != new_total_cards:
                changed_values.append({"field": "total_cards", "from": str(existing_set.total_cards or 0), "to": str(new_total_cards)})

        return {
            "code": code,
            "name": set_name,
            "release_date": new_release_date,
            "total_cards": new_total_cards,
            "label_data": new_label_data,
            "op_type": "create" if existing_set is None else "update",
            "changed_values": changed_values,
        }

    def _build_card_operation(
        self,
        card_item: dict[str, Any],
        extra_map: dict[tuple[str, int], dict[str, Any]],
        mode: str,
    ) -> dict[str, Any] | None:
        """构建卡牌写入动作。"""
        set_code = str(card_item.get("set") or "")
        number = self._normalize_number(card_item.get("number"))
        if not set_code or number is None:
            return None

        extra = extra_map.get((set_code, number), {})
        existing_card = self._repo.get_card_by_set_and_number(set_code, number)

        needs_upsert = existing_card is None or mode == "force"
        if mode == "supplement" and existing_card is not None:
            needs_upsert = False

        # data 字段与历史 sync_metadata.py 逻辑保持一致：写入原始 cards.json 条目
        incoming_card = {
            "set_code": set_code,
            "number": number,
            "name": str(card_item.get("name") or ""),
            "rarity": str(card_item.get("rarity") or ""),
            "image_url": str(card_item.get("image") or ""),
            "element": self._str_or_none(extra.get("element")),
            "type": self._str_or_none(extra.get("type")),
            "stage": self._str_or_none(extra.get("stage")),
            "health": self._normalize_number(extra.get("health")),
            "weakness": self._str_or_none(extra.get("weakness")),
            "retreat_cost": self._normalize_number(extra.get("retreatCost")),
            "data": json.dumps(card_item, ensure_ascii=False),
        }

        changed_fields: list[str] = []
        changed_values: list[dict[str, str]] = []
        if existing_card is None:
            # 新增：不显示 data 字段变化（其他字段已足够）
            changed_fields = [
                "set_code",
                "number",
                "name",
                "rarity",
                "image_url",
                "element",
                "type",
                "stage",
                "health",
                "weakness",
                "retreat_cost",
            ]
            for field in changed_fields:
                changed_values.append(
                    {
                        "field": field,
                        "from": "",
                        "to": str(incoming_card.get(field) or ""),
                    }
                )
        else:
            for field in [
                "name",
                "rarity",
                "image_url",
                "element",
                "type",
                "stage",
                "health",
                "weakness",
                "retreat_cost",
            ]:
                before_value = getattr(existing_card, field)
                after_value = incoming_card[field]
                if before_value != after_value:
                    changed_fields.append(field)
                    changed_values.append(
                        {
                            "field": field,
                            "from": "" if before_value is None else str(before_value),
                            "to": "" if after_value is None else str(after_value),
                        }
                    )

        incoming_pack_names = sorted({str(item) for item in card_item.get("packs", [])})
        existing_pack_names: list[str] = []
        existing_card_id: int | None = None
        if existing_card is not None and existing_card.id is not None:
            existing_card_id = existing_card.id
            existing_pack_names = self._repo.get_card_pack_names(existing_card_id)
        add_pack_names = sorted(set(incoming_pack_names) - set(existing_pack_names))

        if not needs_upsert and not add_pack_names:
            return None

        op_type = "create" if existing_card is None else "update"
        if mode == "force" and existing_card is not None:
            op_type = "force"
        if not needs_upsert and add_pack_names:
            op_type = "link"

        if mode == "force" and existing_card is not None and not changed_values:
            changed_values.append(
                {
                    "field": "__force__",
                    "from": "same",
                    "to": "same",
                }
            )

        return {
            "card": incoming_card,
            "existing_card_id": existing_card_id,
            "needs_upsert": needs_upsert,
            "add_pack_names": add_pack_names,
            "op_type": op_type,
            "changed_fields": changed_fields,
            "changed_values": changed_values,
        }

    def _build_pack_operation(
        self, pack_name: str, set_code: str, mode: str
    ) -> dict[str, Any] | None:
        """构建卡包写入动作。"""
        existing_pack = self._repo.get_pack_by_name(pack_name)
        print(f"[flibustier] pack name={pack_name}, existing={existing_pack is not None}", flush=True)
        if mode == "supplement" and existing_pack is not None:
            print("[flibustier] supplement mode, pack exists, skip", flush=True)
            return None
        if (
            existing_pack is not None
            and existing_pack.set_code == set_code
            and mode != "force"
        ):
            return None

        # 计算字段变化
        changed_values: list[dict[str, str]] = []
        if existing_pack is None:
            # 新增
            changed_values.append({"field": "name", "from": "", "to": pack_name})
            changed_values.append({"field": "set_code", "from": "", "to": set_code})
        else:
            # 更新
            if existing_pack.set_code != set_code:
                changed_values.append({"field": "set_code", "from": existing_pack.set_code or "", "to": set_code})

        return {
            "name": pack_name,
            "set_code": set_code,
            "label_data": json.dumps({"en": pack_name}, ensure_ascii=False),
            "op_type": "create" if existing_pack is None else "update",
            "changed_values": changed_values,
        }

    def _normalize_number(self, value: Any) -> int | None:
        """规范化数字。"""
        try:
            return int(value)
        except (TypeError, ValueError):
            return None

    def _str_or_none(self, value: Any) -> str | None:
        """将值转为字符串或 None。"""
        if value is None:
            return None
        text = str(value)
        return text if text else None
