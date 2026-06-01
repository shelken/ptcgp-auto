# -*- coding: utf-8 -*-
"""元数据同步编排服务。"""

from __future__ import annotations

import json
import uuid
from dataclasses import asdict
from datetime import datetime
from typing import Any

from ptcgp_auto_v2.db.engine import session_scope
from ptcgp_auto_v2.db.models import Card
from ptcgp_auto_v2.db.repositories import CardRepository
from ptcgp_auto_v2.services.metadata_sync.cache_store import TTLCacheStore
from ptcgp_auto_v2.services.metadata_sync.flibustier_sync_service import (
    FlibustierSyncService,
)
from ptcgp_auto_v2.services.metadata_sync.poke52_localization_service import (
    Poke52LocalizationService,
)

# 预览快照缓存（30分钟），避免依赖数据库快照表。
_METADATA_SYNC_PREVIEW_CACHE = TTLCacheStore(ttl_seconds=1800)


def check_sources(
    local_stats: dict[str, int],
    flibustier_stats: dict[str, int],
    poke52_stats: dict[str, int],
) -> dict[str, dict[str, int]]:
    """汇总三方来源检查结果。"""
    return {
        "local": local_stats,
        "flibustier": flibustier_stats,
        "poke52": poke52_stats,
    }


def preview_sync(
    flibustier_service: FlibustierSyncService,
    poke52_service: Poke52LocalizationService,
    repo: CardRepository,
    sync_kind: str,
    source: str,
    mode: str,
    scope_level: str,
    scope_value: str | None,
    force_refresh: bool,
    remote_sets_data: dict[str, list[dict[str, Any]]],
    remote_cards_data: list[dict[str, Any]],
    remote_extra_map: dict[tuple[str, int], dict[str, Any]],
) -> dict[str, Any]:
    """生成预览并写入缓存快照。"""
    flibustier_plan: dict[str, Any] = {
        "mode": mode,
        "scope_level": scope_level,
        "scope_value": scope_value,
        "summary": {
            "upsert_sets": 0,
            "upsert_packs": 0,
            "card_updates": 0,
            "card_pack_links_to_add": 0,
            "card_pack_links_to_remove": 0,
        },
        "operations": {"sets": [], "packs": [], "cards": []},
    }
    if source == "flibustier":
        flibustier_plan = flibustier_service.build_plan(
            mode=mode,
            scope_level=scope_level,
            scope_value=scope_value,
            sets_data=remote_sets_data,
            cards_data=remote_cards_data,
            extra_map=remote_extra_map,
        )

    if sync_kind == "update_new_series":
        flibustier_plan = _keep_new_series_only_plan(flibustier_plan)
    if sync_kind == "update_data":
        flibustier_plan = _keep_data_update_without_zh(flibustier_plan, repo)

    localization_map: dict[str, Any] = {"sets": [], "packs": [], "cards": []}
    if source == "52poke":
        localization_map = poke52_service.build_localization_map(
            scope_level=scope_level,
            scope_value=scope_value,
            force_refresh=force_refresh,
        )

    snapshot_id = uuid.uuid4().hex
    payload = {
        "source": source,
        "mode": mode,
        "sync_kind": sync_kind,
        "scope_level": scope_level,
        "scope_value": scope_value,
        "flibustier": flibustier_plan,
        "localization": localization_map,
    }
    summary = {
        **flibustier_plan.get("summary", {}),
        "localization_sets": len(localization_map.get("sets", [])),
        "localization_packs": len(localization_map.get("packs", [])),
        "localization_cards": len(localization_map.get("cards", [])),
    }

    _METADATA_SYNC_PREVIEW_CACHE.set(
        snapshot_id,
        {
            "payload": payload,
            "summary": summary,
            "scope_level": scope_level,
            "scope_value": scope_value,
            "source": source,
            "mode": mode,
            "created_at": datetime.now().isoformat(),
        },
    )
    preview_items = _build_preview_items(payload, repo)
    result = {
        "snapshot_id": snapshot_id,
        "summary": summary,
        "payload": payload,
        "items": preview_items,
    }

    cached_value = _METADATA_SYNC_PREVIEW_CACHE.get(snapshot_id) or {}
    if isinstance(cached_value, dict):
        cached_value["items"] = preview_items
        _METADATA_SYNC_PREVIEW_CACHE.set(snapshot_id, cached_value)

    return result


def execute_sync(
    flibustier_service: FlibustierSyncService,
    repo: CardRepository,
    snapshot_id: str,
) -> dict[str, Any]:
    """按缓存快照执行同步。"""
    cached_snapshot = _METADATA_SYNC_PREVIEW_CACHE.get(snapshot_id)
    if cached_snapshot is None:
        raise ValueError("预览快照不存在或已过期，请重新生成预览")

    payload = cached_snapshot.get("payload")
    if not isinstance(payload, dict):
        raise ValueError("预览快照数据损坏，请重新生成预览")
    flibustier_result = flibustier_service.execute_plan(
        payload["flibustier"]["operations"]
    )
    localization_result = _apply_localization(
        repo=repo,
        localization=payload.get("localization", {}),
        mode=str(payload.get("mode") or "supplement"),
    )
    return {
        "snapshot_id": snapshot_id,
        "flibustier": flibustier_result,
        "localization": localization_result,
    }


def build_default_check_context() -> dict[str, dict[str, int]]:
    """构建默认检查上下文（读取本地基础统计）。"""
    with session_scope() as session:
        repo = CardRepository(session)
        return check_sources(
            local_stats=repo.get_metadata_counts(),
            flibustier_stats={"sets": 0, "cards": 0},
            poke52_stats={"series": 0, "packs": 0},
        )


def _build_preview_items(
    payload: dict[str, Any], repo: CardRepository | None = None
) -> list[dict[str, str]]:
    """将预览 payload 转换为可读清单。"""
    if repo is None:
        with session_scope() as session:
            return _build_preview_items(payload, CardRepository(session))

    flib = payload.get("flibustier") if isinstance(payload, dict) else {}
    operations = flib.get("operations", {}) if isinstance(flib, dict) else {}
    items: list[dict[str, str]] = []
    items.extend(_build_flibustier_preview_items(operations))
    localization = payload.get("localization") if isinstance(payload, dict) else {}
    if isinstance(localization, dict):
        items.extend(_build_localization_preview_items(localization, repo))
    return items


def _build_flibustier_preview_items(operations: dict[str, Any]) -> list[dict[str, str]]:
    """构建 ptcgp-assets 计划预览清单。"""
    items: list[dict[str, str]] = []
    for set_item in _iter_operation_items(operations, "sets"):
        item = _build_set_operation_preview_item(set_item)
        if item:
            items.append(item)

    for pack_item in _iter_operation_items(operations, "packs"):
        item = _build_pack_operation_preview_item(pack_item)
        if item:
            items.append(item)

    for card_item in _iter_operation_items(operations, "cards"):
        item = _build_card_operation_preview_item(card_item)
        if item:
            items.append(item)
    return items


def _build_localization_preview_items(
    localization: dict[str, Any],
    repo: CardRepository,
) -> list[dict[str, str]]:
    """构建 52poke 本地化预览清单。"""
    items: list[dict[str, str]] = []
    for set_item in _iter_operation_items(localization, "sets"):
        item = _build_set_localization_preview_item(set_item, repo)
        if item:
            items.append(item)

    for pack_item in _iter_operation_items(localization, "packs"):
        item = _build_pack_localization_preview_item(pack_item, repo)
        if item:
            items.append(item)

    for card_item in _iter_operation_items(localization, "cards"):
        item = _build_card_localization_preview_item(card_item, repo)
        if item:
            items.append(item)
    return items


def _iter_operation_items(
    operations: dict[str, Any],
    key: str,
) -> list[dict[str, Any]]:
    """读取操作列表并过滤非法项。"""
    if not isinstance(operations, dict):
        return []
    raw_items = operations.get(key)
    if not isinstance(raw_items, list):
        return []
    return [item for item in raw_items if isinstance(item, dict)]


def _truncate_preview_value(value: Any) -> str:
    """将预览值转成短文本，避免展示过长。"""
    text = str(value or "")
    if len(text) > 40:
        return f"{text[:40]}..."
    return text


def _format_changed_values(
    changed_values: Any,
    *,
    skip_force_flag: bool = False,
) -> list[str]:
    """将 changed_values 转成文本变化列表。"""
    if not isinstance(changed_values, list):
        return []
    changes: list[str] = []
    for val_item in changed_values:
        if not isinstance(val_item, dict):
            continue
        field = str(val_item.get("field") or "")
        if not field:
            continue
        if skip_force_flag and field == "__force__":
            continue
        before_value = _truncate_preview_value(val_item.get("from"))
        after_value = _truncate_preview_value(val_item.get("to"))
        changes.append(f"{field}: '{before_value}' -> '{after_value}'")
    return changes


def _format_card_preview_id(set_code: str, number: Any) -> str:
    """格式化卡牌预览 ID。"""
    try:
        card_number = int(number)
        return f"{set_code}-{card_number:03d}"
    except (TypeError, ValueError):
        return f"{set_code}-{number}"


def _build_set_operation_preview_item(
    set_item: dict[str, Any],
) -> dict[str, str] | None:
    """构建系列操作预览项。"""
    set_code = str(set_item.get("code") or "-")
    set_name = str(set_item.get("name") or "-")
    op_type = str(set_item.get("op_type") or "upsert")
    changes: list[str] = []
    if op_type == "create":
        changes.append(f"新增系列: name='{set_name}'")
    else:
        changed_values = set_item.get("changed_values")
        if isinstance(changed_values, list):
            changes = _format_changed_values(changed_values)
        elif set_item.get("name"):
            changes.append(f"name: '' -> '{set_name}'")
    return {
        "type": "set",
        "id": set_code,
        "name": set_name,
        "action": op_type,
        "changes": " | ".join(changes) if changes else "",
    }


def _build_pack_operation_preview_item(
    pack_item: dict[str, Any],
) -> dict[str, str] | None:
    """构建卡包操作预览项。"""
    pack_name = str(pack_item.get("name") or "-")
    set_code = str(pack_item.get("set_code") or "-")
    op_type = str(pack_item.get("op_type") or "upsert")
    changes: list[str] = []
    if op_type == "create":
        changes.append(f"新增卡包: name='{pack_name}' (系列 '{set_code}')")
    else:
        changes = _format_changed_values(pack_item.get("changed_values"))
    return {
        "type": "pack",
        "id": pack_name,
        "name": pack_name,
        "action": op_type,
        "changes": " | ".join(changes) if changes else "",
    }


def _build_card_operation_preview_item(
    card_item: dict[str, Any],
) -> dict[str, str] | None:
    """构建卡牌操作预览项。"""
    card = card_item.get("card")
    if not isinstance(card, dict):
        return None
    set_code = str(card.get("set_code") or "")
    number = card.get("number")
    card_id = _format_card_preview_id(set_code, number)
    card_name = str(card.get("name") or "-")
    op_type = str(
        card_item.get("op_type")
        or ("upsert" if bool(card_item.get("needs_upsert")) else "link")
    )
    change_parts: list[str] = []

    if op_type == "create":
        change_parts.append(f"新增卡牌: name='{card_name}'")
    elif op_type == "force":
        change_parts.append(f"强制覆盖: name='{card_name}'")

    if op_type != "create":
        change_parts.extend(
            _format_changed_values(
                card_item.get("changed_values"),
                skip_force_flag=True,
            )
        )

    if bool(card_item.get("add_pack_names")):
        add_links = ",".join(str(name) for name in card_item.get("add_pack_names", []))
        if add_links:
            change_parts.append(f"添加卡包关联: +{add_links}")

    return {
        "type": "card",
        "id": card_id,
        "name": card_name,
        "action": op_type,
        "changes": " | ".join(change_parts),
    }


def _build_set_localization_preview_item(
    set_item: dict[str, Any],
    repo: CardRepository,
) -> dict[str, str] | None:
    """构建系列中文本地化预览项。"""
    set_code = str(set_item.get("set_code") or "-")
    zh_value = str(set_item.get("zh") or "")
    card_set = repo.get_set_by_code(set_code)
    old_zh = _extract_label_zh(getattr(card_set, "label_data", None))
    if old_zh == zh_value:
        return None
    return {
        "type": "set",
        "id": set_code,
        "name": zh_value or "-",
        "action": "localize",
        "fields": "label_data.zh",
        "changes": f"zh: '{old_zh}' -> '{zh_value}'" if zh_value else "",
    }


def _build_pack_localization_preview_item(
    pack_item: dict[str, Any],
    repo: CardRepository,
) -> dict[str, str] | None:
    """构建卡包中文本地化预览项。"""
    pack_name = str(pack_item.get("pack_name") or "-")
    zh_value = str(pack_item.get("zh") or "")
    pack = repo.get_pack_by_name(pack_name)
    old_zh = _extract_label_zh(getattr(pack, "label_data", None))
    if old_zh == zh_value:
        return None
    return {
        "type": "pack",
        "id": pack_name,
        "name": zh_value or "-",
        "action": "localize",
        "fields": "label_data.zh",
        "changes": f"zh: '{old_zh}' -> '{zh_value}'" if zh_value else "",
    }


def _build_card_localization_preview_item(
    card_item: dict[str, Any],
    repo: CardRepository,
) -> dict[str, str] | None:
    """构建卡牌中文本地化预览项。"""
    set_code = str(card_item.get("set_code") or "")
    number = card_item.get("number")
    card_id = _format_card_preview_id(set_code, number)
    zh_name = str(card_item.get("localized_name") or "")
    old_zh = _extract_card_localized_zh(repo, set_code, number)
    if old_zh == zh_name:
        return None
    return {
        "type": "card",
        "id": card_id,
        "name": zh_name or "-",
        "action": "localize",
        "fields": "data.localized_name.zh",
        "changes": f"localized_name.zh: '{old_zh}' -> '{zh_name}'" if zh_name else "",
    }


def _extract_label_zh(raw_label: str | None) -> str:
    """从 label_data 中读取 zh。"""
    labels = _parse_json_dict(raw_label)
    return str(labels.get("zh") or "")


def _extract_card_localized_zh(
    repo: CardRepository,
    set_code: str,
    number: Any,
) -> str:
    """从卡牌 data 中读取 localized_name.zh。"""
    try:
        card_num = int(number)
    except (TypeError, ValueError):
        return ""
    if not set_code or not card_num:
        return ""
    card = repo.get_card_by_set_and_number(set_code, card_num)
    if card is None:
        return ""
    data = _parse_json_dict(card.data)
    localized_name = data.get("localized_name")
    if not isinstance(localized_name, dict):
        return ""
    return str(localized_name.get("zh") or "")


def _apply_localization(
    repo: CardRepository,
    localization: dict[str, list[dict[str, Any]]],
    mode: str,
) -> dict[str, int]:
    """应用 52poke 本地化写入。"""
    set_updates = sum(
        1
        for item in _iter_operation_items(localization, "sets")
        if _apply_set_localization_item(repo, item, mode)
    )
    pack_updates = sum(
        1
        for item in _iter_operation_items(localization, "packs")
        if _apply_pack_localization_item(repo, item, mode)
    )
    card_updates = sum(
        1
        for item in _iter_operation_items(localization, "cards")
        if _apply_card_localization_item(repo, item, mode)
    )

    return {
        "set_label_updates": set_updates,
        "pack_label_updates": pack_updates,
        "card_name_updates": card_updates,
    }


def _apply_set_localization_item(
    repo: CardRepository,
    item: dict[str, Any],
    mode: str,
) -> bool:
    """应用单条系列本地化。"""
    set_code = str(item.get("set_code") or "")
    zh_value = str(item.get("zh") or "").strip()
    if not set_code or not zh_value:
        return False
    card_set = repo.get_set_by_code(set_code)
    if card_set is None:
        return False
    labels = _parse_json_dict(card_set.label_data)
    current_zh = str(labels.get("zh") or "").strip()
    if mode == "supplement" and current_zh:
        return False
    if current_zh == zh_value:
        return False
    labels["zh"] = zh_value
    return bool(repo.update_set_label(set_code, json.dumps(labels, ensure_ascii=False)))


def _apply_pack_localization_item(
    repo: CardRepository,
    item: dict[str, Any],
    mode: str,
) -> bool:
    """应用单条卡包本地化。"""
    pack_name = str(item.get("pack_name") or "")
    zh_value = str(item.get("zh") or "").strip()
    if not pack_name or not zh_value:
        return False
    pack = repo.get_pack_by_name(pack_name)
    if pack is None:
        return False
    labels = _parse_json_dict(pack.label_data)
    current_zh = str(labels.get("zh") or "").strip()
    if mode == "supplement" and current_zh:
        return False
    if current_zh == zh_value:
        return False
    labels["zh"] = zh_value
    return bool(
        repo.update_pack_label(pack_name, json.dumps(labels, ensure_ascii=False))
    )


def _apply_card_localization_item(
    repo: CardRepository,
    item: dict[str, Any],
    mode: str,
) -> bool:
    """应用单条卡牌本地化。"""
    set_code = str(item.get("set_code") or "")
    number = item.get("number")
    zh_name = str(item.get("localized_name") or "").strip()
    if not set_code or zh_name == "":
        return False
    try:
        card_number = int(number)
    except (TypeError, ValueError):
        return False

    card = repo.get_card_by_set_and_number(set_code, card_number)
    if card is None:
        return False
    data = _parse_json_dict(card.data)
    localized_name = data.get("localized_name")
    if not isinstance(localized_name, dict):
        localized_name = {}
    current_zh = str(localized_name.get("zh") or "").strip()
    if mode == "supplement" and current_zh:
        return False
    if current_zh == zh_name:
        return False

    localized_name["zh"] = zh_name
    data["localized_name"] = localized_name
    card_payload = asdict(card)
    card_payload["data"] = json.dumps(data, ensure_ascii=False)
    repo.upsert_card(Card.model_validate(card_payload))
    return True


def _parse_json_dict(raw: str | None) -> dict[str, Any]:
    """安全解析 JSON 字典。"""
    if not raw:
        return {}
    try:
        value = json.loads(raw)
    except (TypeError, ValueError):
        return {}
    if isinstance(value, dict):
        return value
    return {}


def _keep_new_series_only_plan(flibustier_plan: dict[str, Any]) -> dict[str, Any]:
    """仅保留新增系列及其关联 pack/card 动作。"""
    operations = flibustier_plan.get("operations")
    if not isinstance(operations, dict):
        return flibustier_plan

    raw_sets = operations.get("sets")
    if not isinstance(raw_sets, list):
        raw_sets = []
    create_sets = [
        item
        for item in raw_sets
        if isinstance(item, dict) and str(item.get("op_type") or "") == "create"
    ]
    create_set_codes = {
        str(item.get("code") or "")
        for item in create_sets
        if isinstance(item, dict) and str(item.get("code") or "")
    }

    raw_packs = operations.get("packs")
    packs = raw_packs if isinstance(raw_packs, list) else []
    create_packs = [
        item
        for item in packs
        if isinstance(item, dict)
        and str(item.get("set_code") or "") in create_set_codes
    ]

    raw_cards = operations.get("cards")
    cards = raw_cards if isinstance(raw_cards, list) else []
    create_cards = []
    for item in cards:
        if not isinstance(item, dict):
            continue
        card = item.get("card")
        if not isinstance(card, dict):
            continue
        if str(card.get("set_code") or "") in create_set_codes:
            create_cards.append(item)

    filtered_plan = dict(flibustier_plan)
    filtered_plan["operations"] = {
        "sets": create_sets,
        "packs": create_packs,
        "cards": create_cards,
    }
    filtered_plan["summary"] = _build_flibustier_summary(filtered_plan["operations"])
    return filtered_plan


def _keep_data_update_without_zh(
    flibustier_plan: dict[str, Any],
    repo: CardRepository,
) -> dict[str, Any]:
    """更新数据时保留本地中文字段。"""
    operations = flibustier_plan.get("operations")
    if not isinstance(operations, dict):
        return flibustier_plan

    for item in _iter_operation_items(operations, "sets"):
        _preserve_set_label_zh(item, repo)
    for item in _iter_operation_items(operations, "packs"):
        _preserve_pack_label_zh(item, repo)
    for item in _iter_operation_items(operations, "cards"):
        _preserve_card_data_zh(item, repo)

    return flibustier_plan


def _preserve_set_label_zh(item: dict[str, Any], repo: CardRepository) -> None:
    """保留系列 label_data.zh。"""
    set_code = str(item.get("code") or "")
    if not set_code:
        return
    current_set = repo.get_set_by_code(set_code)
    if current_set is None:
        return
    current_label = _parse_json_dict(current_set.label_data)
    current_zh = str(current_label.get("zh") or "").strip()
    if not current_zh:
        return
    target_label = _parse_json_dict(str(item.get("label_data") or "{}"))
    target_label["zh"] = current_zh
    item["label_data"] = json.dumps(target_label, ensure_ascii=False)


def _preserve_pack_label_zh(item: dict[str, Any], repo: CardRepository) -> None:
    """保留卡包 label_data.zh。"""
    pack_name = str(item.get("name") or "")
    if not pack_name:
        return
    current_pack = repo.get_pack_by_name(pack_name)
    if current_pack is None:
        return
    current_label = _parse_json_dict(current_pack.label_data)
    current_zh = str(current_label.get("zh") or "").strip()
    if not current_zh:
        return
    target_label = _parse_json_dict(str(item.get("label_data") or "{}"))
    target_label["zh"] = current_zh
    item["label_data"] = json.dumps(target_label, ensure_ascii=False)


def _preserve_card_data_zh(item: dict[str, Any], repo: CardRepository) -> None:
    """保留卡牌 data.localized_name.zh。"""
    card = item.get("card")
    if not isinstance(card, dict):
        return
    set_code = str(card.get("set_code") or "")
    number = card.get("number")
    try:
        card_number = int(number)
    except (TypeError, ValueError):
        return
    current_card = repo.get_card_by_set_and_number(set_code, card_number)
    if current_card is None:
        return

    current_data = _parse_json_dict(current_card.data)
    current_loc = current_data.get("localized_name")
    if not isinstance(current_loc, dict):
        return
    current_zh = str(current_loc.get("zh") or "").strip()
    if not current_zh:
        return

    target_data = _parse_json_dict(str(card.get("data") or "{}"))
    target_loc = target_data.get("localized_name")
    if not isinstance(target_loc, dict):
        target_loc = {}
    target_loc["zh"] = current_zh
    target_data["localized_name"] = target_loc
    card["data"] = json.dumps(target_data, ensure_ascii=False)


def _build_flibustier_summary(operations: dict[str, Any]) -> dict[str, int]:
    """按 operations 重新计算 flibustier 摘要。"""
    sets_raw = operations.get("sets")
    packs_raw = operations.get("packs")
    cards_raw = operations.get("cards")
    sets = sets_raw if isinstance(sets_raw, list) else []
    packs = packs_raw if isinstance(packs_raw, list) else []
    cards = cards_raw if isinstance(cards_raw, list) else []
    return {
        "upsert_sets": len(sets),
        "upsert_packs": len(packs),
        "card_updates": sum(
            1
            for item in cards
            if isinstance(item, dict) and bool(item.get("needs_upsert"))
        ),
        "card_pack_links_to_add": sum(
            len(item.get("add_pack_names", []))
            for item in cards
            if isinstance(item, dict) and isinstance(item.get("add_pack_names"), list)
        ),
        "card_pack_links_to_remove": 0,
    }
