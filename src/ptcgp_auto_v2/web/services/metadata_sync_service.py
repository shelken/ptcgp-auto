# -*- coding: utf-8 -*-
"""元数据同步编排服务。"""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timedelta
from typing import Any

from ptcgp_auto_v2.db.repositories import CardRepository
from ptcgp_auto_v2.db.repositories.metadata_sync_snapshot_repository import (
    MetadataSyncSnapshotRepository,
)
from ptcgp_auto_v2.services.metadata_sync.flibustier_sync_service import (
    FlibustierSyncService,
)
from ptcgp_auto_v2.services.metadata_sync.poke52_localization_service import (
    Poke52LocalizationService,
)


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
    snapshot_repo: MetadataSyncSnapshotRepository,
    flibustier_service: FlibustierSyncService,
    poke52_service: Poke52LocalizationService,
    source: str,
    mode: str,
    scope_level: str,
    scope_value: str | None,
    force_refresh: bool,
    remote_sets_data: dict[str, list[dict[str, Any]]],
    remote_cards_data: list[dict[str, Any]],
    remote_extra_map: dict[tuple[str, int], dict[str, Any]],
) -> dict[str, Any]:
    """生成预览并保存快照。"""
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
    if source in {"full", "flibustier"}:
        flibustier_plan = flibustier_service.build_plan(
            mode=mode,
            scope_level=scope_level,
            scope_value=scope_value,
            sets_data=remote_sets_data,
            cards_data=remote_cards_data,
            extra_map=remote_extra_map,
        )

    localization_map: dict[str, Any] = {"sets": [], "packs": [], "cards": []}
    if source in {"full", "52poke"}:
        localization_map = poke52_service.build_localization_map(
            scope_level=scope_level,
            scope_value=scope_value,
            force_refresh=force_refresh,
        )

    snapshot_id = uuid.uuid4().hex
    payload = {
        "source": source,
        "mode": mode,
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

    snapshot_repo.create_snapshot(
        snapshot_id=snapshot_id,
        scope_level=scope_level,
        scope_value=scope_value,
        source=source,
        mode=mode,
        payload_json=json.dumps(payload, ensure_ascii=False),
        summary_json=json.dumps(summary, ensure_ascii=False),
        expires_at=datetime.now() + timedelta(minutes=30),
    )
    return {
        "snapshot_id": snapshot_id,
        "summary": summary,
        "payload": payload,
    }


def execute_sync(
    snapshot_repo: MetadataSyncSnapshotRepository,
    flibustier_service: FlibustierSyncService,
    snapshot_id: str,
) -> dict[str, Any]:
    """按快照执行同步。"""
    snapshot = snapshot_repo.get_snapshot(snapshot_id)
    if snapshot is None:
        raise ValueError("快照不存在或已过期")

    payload = json.loads(snapshot.payload_json)
    flibustier_result = flibustier_service.execute_plan(
        payload["flibustier"]["operations"]
    )
    localization_result = _apply_localization(
        repo=CardRepository(),
        localization=payload.get("localization", {}),
        mode=str(payload.get("mode") or "supplement"),
    )
    snapshot_repo.mark_executed(snapshot_id)
    return {
        "snapshot_id": snapshot_id,
        "flibustier": flibustier_result,
        "localization": localization_result,
    }


def build_default_check_context() -> dict[str, dict[str, int]]:
    """构建默认检查上下文（读取本地基础统计）。"""
    repo = CardRepository()
    local_stats = {
        "sets": len(repo.get_all_sets()),
        "packs": len(repo.get_all_packs()),
        "cards": sum(
            len(repo.get_cards_by_set(item.code)) for item in repo.get_all_sets()
        ),
    }
    return check_sources(
        local_stats=local_stats,
        flibustier_stats={"sets": 0, "cards": 0},
        poke52_stats={"series": 0, "packs": 0},
    )


def _apply_localization(
    repo: CardRepository,
    localization: dict[str, list[dict[str, Any]]],
    mode: str,
) -> dict[str, int]:
    """应用 52poke 本地化写入。"""
    set_updates = 0
    pack_updates = 0
    card_updates = 0

    for item in localization.get("sets", []):
        set_code = str(item.get("set_code") or "")
        zh_value = str(item.get("zh") or "").strip()
        if not set_code or not zh_value:
            continue
        card_set = repo.get_set_by_code(set_code)
        if card_set is None:
            continue
        labels = _parse_json_dict(card_set.label_data)
        current_zh = str(labels.get("zh") or "").strip()
        if mode == "supplement" and current_zh:
            continue
        if current_zh == zh_value:
            continue
        labels["zh"] = zh_value
        if repo.update_set_label(set_code, json.dumps(labels, ensure_ascii=False)):
            set_updates += 1

    for item in localization.get("packs", []):
        pack_name = str(item.get("pack_name") or "")
        zh_value = str(item.get("zh") or "").strip()
        if not pack_name or not zh_value:
            continue
        pack = repo.get_pack_by_name(pack_name)
        if pack is None:
            continue
        labels = _parse_json_dict(pack.label_data)
        current_zh = str(labels.get("zh") or "").strip()
        if mode == "supplement" and current_zh:
            continue
        if current_zh == zh_value:
            continue
        labels["zh"] = zh_value
        if repo.update_pack_label(pack_name, json.dumps(labels, ensure_ascii=False)):
            pack_updates += 1

    for item in localization.get("cards", []):
        set_code = str(item.get("set_code") or "")
        number = item.get("number")
        zh_name = str(item.get("localized_name") or "").strip()
        if not set_code or zh_name == "":
            continue
        try:
            card_number = int(number)
        except (TypeError, ValueError):
            continue
        card = repo.get_card_by_set_and_number(set_code, card_number)
        if card is None:
            continue

        data = _parse_json_dict(card.data)
        localized_name = data.get("localized_name")
        if not isinstance(localized_name, dict):
            localized_name = {}
        current_zh = str(localized_name.get("zh") or "").strip()
        if mode == "supplement" and current_zh:
            continue
        if current_zh == zh_name:
            continue

        localized_name["zh"] = zh_name
        data["localized_name"] = localized_name
        card.data = json.dumps(data, ensure_ascii=False)
        repo.upsert_card(card)
        card_updates += 1

    return {
        "set_label_updates": set_updates,
        "pack_label_updates": pack_updates,
        "card_name_updates": card_updates,
    }


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
