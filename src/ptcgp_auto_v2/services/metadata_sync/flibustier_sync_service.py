# -*- coding: utf-8 -*-
"""ptcgp-assets 元数据同步服务。

历史类名仍保留 FlibustierSyncService，避免扩大 Web/API 调用方改动范围。
"""

from __future__ import annotations

import copy
import json
from dataclasses import dataclass
from typing import Any

import requests

from ptcgp_auto_v2.config.assets import build_pack_image_url
from ptcgp_auto_v2.db.models import Card, CardSet, Pack
from ptcgp_auto_v2.db.repositories import CardRepository
from ptcgp_auto_v2.services.metadata_sync.cache_store import TTLCacheStore

ASSETS_METADATA_BASE_URL = "https://raw.githubusercontent.com/shelken/ptcgp-assets/main/metadata"
# 变更原因: sets 切换到 ptcgp-assets，避免继续依赖 flibustier 补齐系列元数据。
SETS_URL = f"{ASSETS_METADATA_BASE_URL}/sets/en-US/sets.json"
# 变更原因: cards.extra 已覆盖同步所需全部卡牌字段，继续拉 flibustier cards.json 会丢失游戏已有卡。
CARDS_EXTRA_URL = f"{ASSETS_METADATA_BASE_URL}/cards/en-US/cards.extra.json"


@dataclass(frozen=True, slots=True)
class PackMetadata:
    name: str
    set_code: str
    sku_id: str | None
    image_url: str | None


class FlibustierSyncService:
    """负责构建 ptcgp-assets 同步预览计划并执行。"""

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
        pack_universe = self._build_pack_universe(all_sets)
        filtered_sets, filtered_cards = self._filter_scope(
            scope_level=scope_level,
            scope_value=scope_value,
            all_sets=all_sets,
            all_cards=cards_data,
            pack_universe=pack_universe,
        )
        filtered_pack_universe = self._build_pack_universe(filtered_sets)

        operations: dict[str, Any] = {"sets": [], "packs": [], "cards": []}

        # card / pack 级同步只关注目标对象，避免把系列更新混入预览结果。
        include_set_operations = scope_level in {"all", "set"}
        if include_set_operations:
            for set_item in filtered_sets:
                op = self._build_set_operation(set_item, mode)
                if op is not None:
                    operations["sets"].append(op)

        planned_pack_names: set[str] = set()
        for pack_name, pack_metadata in filtered_pack_universe.items():
            pack_op = self._build_pack_operation(pack_metadata, mode)
            planned_pack_names.add(pack_name)
            if pack_op is not None:
                operations["packs"].append(pack_op)

        for card_item in filtered_cards:
            card_op = self._build_card_operation(card_item, extra_map, mode)
            if card_op is None:
                continue
            # 变更原因：scope 内 pack 操作只写当前范围，card-pack link 仍应保留 sets universe 中已知的跨 set 获取来源。
            card_op["add_pack_names"] = [
                pack_name
                for pack_name in card_op["add_pack_names"]
                if pack_name in pack_universe
            ]
            if not card_op["needs_upsert"] and not card_op["add_pack_names"]:
                continue
            for pack_name in card_op["add_pack_names"]:
                if pack_name in planned_pack_names:
                    continue
                # 变更原因：scoped sync 保留跨 set link 时，也必须计划对应 pack row，避免执行后产生悬空 card_packs。
                pack_op = self._build_pack_operation(pack_universe[pack_name], mode)
                planned_pack_names.add(pack_name)
                if pack_op is not None:
                    operations["packs"].append(pack_op)
            operations["cards"].append(card_op)

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
        """抓取远端元数据。"""
        cache_key = "ptcgp-assets:remote_metadata:v2"
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

            extra_response = requests.get(CARDS_EXTRA_URL, timeout=60)
            extra_response.raise_for_status()
            cards_data = extra_response.json()
        except Exception as exc:  # pragma: no cover - 网络异常分支
            raise RuntimeError(f"拉取 ptcgp-assets 元数据失败: {exc}") from exc

        extra_map: dict[tuple[str, int], dict[str, Any]] = {}
        for item in cards_data:
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

        for pack_data in operations.get("packs", []):
            # 变更原因：card-pack link 只应指向已知 pack，先写 pack universe 再写 link。
            self._repo.upsert_pack_safe(Pack.model_validate(pack_data))
            pack_count += 1

        for card_item in operations.get("cards", []):
            card_model = Card.model_validate(card_item["card"])
            card_id: int | None = card_item.get("existing_card_id")
            if card_item.get("needs_upsert"):
                card_id = self._repo.upsert_card(card_model)
                card_count += 1

            if card_id is None:
                continue
            for pack_name in card_item.get("add_pack_names", []):
                self._repo.add_card_pack(card_id, pack_name)
                link_count += 1

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
        pack_universe: dict[str, PackMetadata],
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
            if pack_name not in pack_universe:
                return [], []
            # 变更原因：pack 所属 set 只能由 sets.json.packs 决定，不能由含该 pack 的卡牌所属系列反推。
            set_code = pack_universe[pack_name].set_code
            cards = [
                item
                for item in all_cards
                if pack_name in [str(name) for name in item.get("packs", [])]
            ]
            sets = [item for item in all_sets if str(item.get("code")) == set_code]
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

    def _build_pack_universe(self, sets: list[dict[str, Any]]) -> dict[str, PackMetadata]:
        """从 sets.json.packs 建立 pack 到 set 的唯一归属。"""
        pack_universe: dict[str, PackMetadata] = {}
        for set_item in sets:
            set_code = str(set_item.get("code") or "").strip()
            if not set_code:
                continue
            for raw_pack_entry in set_item.get("packs") or []:
                pack_entry = self._parse_pack_entry(raw_pack_entry, set_code)
                if pack_entry.name in pack_universe and pack_universe[pack_entry.name].set_code != set_code:
                    raise ValueError(
                        f"pack name belongs to multiple sets: {pack_entry.name} "
                        f"({pack_universe[pack_entry.name].set_code} vs {set_code})"
                    )
                pack_universe[pack_entry.name] = pack_entry
        return pack_universe

    def _parse_pack_entry(self, raw_pack_entry: Any, set_code: str) -> PackMetadata:
        """兼容 sets.json.packs 旧 string 与新 object entry。"""
        if isinstance(raw_pack_entry, str):
            clean_pack_name = raw_pack_entry.strip()
            if not clean_pack_name:
                raise ValueError(f"sets.json pack 名称为空: {set_code}")
            return PackMetadata(clean_pack_name, set_code, None, None)

        if not isinstance(raw_pack_entry, dict):
            raise ValueError(f"sets.json pack entry 格式错误: {raw_pack_entry}")
        clean_pack_name = str(raw_pack_entry.get("name") or "").strip()
        if not clean_pack_name:
            raise ValueError(f"sets.json pack object 缺少 name: {raw_pack_entry}")
        sku_id = self._str_or_none(raw_pack_entry.get("skuId"))
        image_url = build_pack_image_url(sku_id) if sku_id else None
        return PackMetadata(clean_pack_name, set_code, sku_id, image_url)

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
        print(f"[ptcgp-assets] set code={code}, existing={existing_set is not None}", flush=True)
        if mode == "supplement" and existing_set is not None:
            print("[ptcgp-assets] supplement mode, set exists, skip", flush=True)
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
            # 变更原因: ptcgp-assets 按运行语言输出 name，缺 en/zh 时应使用真实非空名称而不是退回 code。
            set_name = str(
                incoming_name.get("en")
                or incoming_name.get("zh")
                or next(
                    (
                        value
                        for value in incoming_name.values()
                        if isinstance(value, str) and value.strip()
                    ),
                    code,
                )
            )
        else:
            set_name = str(incoming_name)
            label_dict.setdefault("en", set_name)

        # 计算字段变化
        changed_values: list[dict[str, str]] = []
        incoming_release_date = set_item.get("releaseDate")
        # 变更原因：游戏导出的 sets.json 不提供发布日期，force 同步不能用 null 清空本地维护的日期。
        new_release_date = (
            existing_set.release_date
            if existing_set is not None and incoming_release_date is None
            else incoming_release_date
        )
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

        # 变更原因: cards.extra 已替代 cards.json，data 保存当前游戏 MemoryDatabase 转换后的完整卡牌条目。
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
            # 变更原因：supplement 不更新已有卡字段，link-only 预览不应混入字段变化噪音。
            if mode == "supplement":
                changed_fields = []
                changed_values = []

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
        self, pack_metadata: PackMetadata, mode: str
    ) -> dict[str, Any] | None:
        """构建卡包写入动作。"""
        pack_name = pack_metadata.name
        existing_pack = self._repo.get_pack_by_name(pack_name)
        print(f"[ptcgp-assets] pack name={pack_name}, existing={existing_pack is not None}", flush=True)
        missing_asset_fields = (
            existing_pack is not None
            and (
                (pack_metadata.sku_id and not getattr(existing_pack, "sku_id", None))
                or (pack_metadata.image_url and not getattr(existing_pack, "image_url", None))
            )
        )
        if mode == "supplement" and existing_pack is not None and not missing_asset_fields:
            print("[ptcgp-assets] supplement mode, pack exists, skip", flush=True)
            return None
        if (
            existing_pack is not None
            and existing_pack.set_code == pack_metadata.set_code
            and not missing_asset_fields
            and mode != "force"
        ):
            return None

        # 计算字段变化
        changed_values: list[dict[str, str]] = []
        if existing_pack is None:
            # 新增
            changed_values.append({"field": "name", "from": "", "to": pack_name})
            changed_values.append({"field": "set_code", "from": "", "to": pack_metadata.set_code})
            if pack_metadata.sku_id:
                changed_values.append({"field": "sku_id", "from": "", "to": pack_metadata.sku_id})
            if pack_metadata.image_url:
                changed_values.append({"field": "image_url", "from": "", "to": pack_metadata.image_url})
        else:
            # 更新
            if existing_pack.set_code != pack_metadata.set_code:
                changed_values.append({"field": "set_code", "from": existing_pack.set_code or "", "to": pack_metadata.set_code})
            if pack_metadata.sku_id and getattr(existing_pack, "sku_id", None) != pack_metadata.sku_id:
                changed_values.append({"field": "sku_id", "from": getattr(existing_pack, "sku_id", None) or "", "to": pack_metadata.sku_id})
            if pack_metadata.image_url and getattr(existing_pack, "image_url", None) != pack_metadata.image_url:
                changed_values.append({"field": "image_url", "from": getattr(existing_pack, "image_url", None) or "", "to": pack_metadata.image_url})

        return {
            "name": pack_name,
            "set_code": pack_metadata.set_code,
            "label_data": json.dumps({"en": pack_name}, ensure_ascii=False),
            "sku_id": pack_metadata.sku_id,
            "image_url": pack_metadata.image_url,
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
