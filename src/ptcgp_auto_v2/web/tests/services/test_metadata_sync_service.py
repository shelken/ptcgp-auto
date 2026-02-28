# -*- coding: utf-8 -*-
"""metadata_sync_service 单元测试。"""

from __future__ import annotations

from ptcgp_auto_v2.web.services.metadata_sync_service import (
    _METADATA_SYNC_PREVIEW_CACHE,
    check_sources,
    execute_sync,
    preview_sync,
)


class _FakeFlibustierSyncService:
    """flibustier 服务桩。"""

    def build_plan(self, **_kwargs):
        return {
            "mode": "force",
            "scope_level": "set",
            "scope_value": "A1",
            "summary": {
                "upsert_sets": 1,
                "upsert_packs": 1,
                "card_updates": 1,
                "card_pack_links_to_add": 1,
                "card_pack_links_to_remove": 0,
            },
            "operations": {
                "sets": [
                    {
                        "code": "A1",
                        "name": "A1",
                        "release_date": None,
                        "total_cards": 0,
                        "label_data": "{}",
                    }
                ],
                "packs": [{"name": "PackA", "set_code": "A1", "label_data": "{}"}],
                "cards": [
                    {
                        "card": {
                            "set_code": "A1",
                            "number": 1,
                            "name": "CardA",
                            "rarity": "C",
                            "image_url": "a.webp",
                            "element": None,
                            "type": None,
                            "stage": None,
                            "health": None,
                            "weakness": None,
                            "retreat_cost": None,
                            "data": "{}",
                        },
                        "existing_card_id": None,
                        "needs_upsert": True,
                        "add_pack_names": ["PackA"],
                    }
                ],
            },
        }

    def execute_plan(self, operations):
        assert "sets" in operations
        return {
            "upsert_sets": 1,
            "upsert_packs": 1,
            "card_updates": 1,
            "card_pack_links_to_add": 1,
            "card_pack_links_to_remove": 0,
        }


class _FakePoke52Service:
    """52poke 服务桩。"""

    def build_localization_map(self, **_kwargs):
        return {
            "sets": [{"set_code": "A1", "zh": "最强的基因"}],
            "packs": [{"set_code": "A1", "pack_name": "PackA", "zh": "最强的基因"}],
            "cards": [{"set_code": "A1", "number": 1, "localized_name": "妙蛙种子"}],
        }


def test_preview_sync_only_52poke_source_skips_flibustier_build() -> None:
    """source=52poke 时不应调用 flibustier build_plan。"""

    class _Only52PokeFlibustier:
        def build_plan(self, **_kwargs):
            raise AssertionError("source=52poke 不应触发 flibustier build_plan")

    result = preview_sync(
        flibustier_service=_Only52PokeFlibustier(),  # type: ignore[arg-type]
        poke52_service=_FakePoke52Service(),
        sync_kind="update_chinese",
        source="52poke",
        mode="supplement",
        scope_level="set",
        scope_value="A1",
        force_refresh=False,
        remote_sets_data={},
        remote_cards_data=[],
        remote_extra_map={},
    )

    assert result["summary"]["upsert_sets"] == 0
    assert result["summary"]["localization_sets"] == 1


def test_check_sources_contains_three_channels() -> None:
    """检查结果应包含本地/flibustier/52poke 三个来源。"""
    result = check_sources(
        local_stats={"sets": 16, "packs": 38, "cards": 2777},
        flibustier_stats={"sets": 17, "cards": 2916},
        poke52_stats={"series": 2, "packs": 17},
    )
    assert result["local"]["sets"] == 16
    assert result["flibustier"]["sets"] == 17
    assert result["poke52"]["series"] == 2


def test_preview_sync_creates_snapshot_with_summary() -> None:
    """预览应生成缓存快照并返回 summary。"""
    result = preview_sync(
        flibustier_service=_FakeFlibustierSyncService(),
        poke52_service=_FakePoke52Service(),
        sync_kind="update_data",
        source="flibustier",
        mode="force",
        scope_level="set",
        scope_value="A1",
        force_refresh=False,
        remote_sets_data={"main": []},
        remote_cards_data=[],
        remote_extra_map={},
    )

    assert result["snapshot_id"]
    assert result["summary"]["upsert_sets"] == 1
    cached = _METADATA_SYNC_PREVIEW_CACHE.get(result["snapshot_id"])
    assert isinstance(cached, dict)
    payload = cached.get("payload", {})
    assert isinstance(payload, dict)
    assert payload["flibustier"]["summary"]["upsert_sets"] == 1


def test_execute_sync_rejects_missing_snapshot() -> None:
    """不存在快照时应抛出错误。"""
    try:
        execute_sync(
            flibustier_service=_FakeFlibustierSyncService(),
            snapshot_id="not-found",
        )
        assert False, "预期应抛出 ValueError"
    except ValueError as exc:
        assert "不存在或已过期" in str(exc)


def test_execute_sync_applies_localization_in_supplement_mode() -> None:
    """执行同步时应写入 52poke 本地化（supplement）。"""
    flib = _FakeFlibustierSyncService()
    preview = preview_sync(
        flibustier_service=flib,
        poke52_service=_FakePoke52Service(),
        sync_kind="update_data",
        source="flibustier",
        mode="supplement",
        scope_level="set",
        scope_value="A1",
        force_refresh=False,
        remote_sets_data={"main": []},
        remote_cards_data=[],
        remote_extra_map={},
    )

    result = execute_sync(
        flibustier_service=flib,
        snapshot_id=preview["snapshot_id"],
    )

    assert result["localization"]["set_label_updates"] >= 0
    assert result["localization"]["pack_label_updates"] >= 0
    assert result["localization"]["card_name_updates"] >= 0


def test_check_sources_keeps_all_channels() -> None:
    """check_sources 返回结构应保持三来源键。"""
    result = check_sources(
        local_stats={"sets": 1, "packs": 1, "cards": 1},
        flibustier_stats={"sets": 2, "cards": 2},
        poke52_stats={"series": 3, "packs": 4},
    )
    assert set(result.keys()) == {"local", "flibustier", "poke52"}


def test_preview_sync_new_series_only_keeps_new_set_operations() -> None:
    """更新新系列预览应保留新增系列及其关联 pack/card 更新。"""

    class _NewSeriesFlibustier:
        def build_plan(self, **_kwargs):
            return {
                "mode": "supplement",
                "scope_level": "all",
                "scope_value": None,
                "summary": {
                    "upsert_sets": 2,
                    "upsert_packs": 1,
                    "card_updates": 1,
                    "card_pack_links_to_add": 1,
                    "card_pack_links_to_remove": 0,
                },
                "operations": {
                    "sets": [
                        {"code": "A1", "name": "old", "op_type": "update"},
                        {"code": "A2", "name": "new", "op_type": "create"},
                    ],
                    "packs": [{"name": "PackA", "set_code": "A2"}],
                    "cards": [
                        {
                            "card": {
                                "set_code": "A2",
                                "number": 1,
                                "name": "CardA",
                                "rarity": "C",
                                "image_url": "a.webp",
                                "data": "{}",
                            },
                            "existing_card_id": None,
                            "needs_upsert": True,
                            "add_pack_names": ["PackA"],
                        }
                    ],
                },
            }

    result = preview_sync(
        flibustier_service=_NewSeriesFlibustier(),  # type: ignore[arg-type]
        poke52_service=_FakePoke52Service(),
        sync_kind="update_new_series",
        source="flibustier",
        mode="supplement",
        scope_level="all",
        scope_value=None,
        force_refresh=False,
        remote_sets_data={},
        remote_cards_data=[],
        remote_extra_map={},
    )

    payload = result["payload"]
    assert len(payload["flibustier"]["operations"]["sets"]) == 1
    assert payload["flibustier"]["operations"]["sets"][0]["code"] == "A2"
    assert len(payload["flibustier"]["operations"]["packs"]) == 1
    assert payload["flibustier"]["operations"]["packs"][0]["set_code"] == "A2"
    assert len(payload["flibustier"]["operations"]["cards"]) == 1
    assert payload["flibustier"]["operations"]["cards"][0]["card"]["set_code"] == "A2"
    assert result["summary"]["upsert_sets"] == 1
    assert result["summary"]["upsert_packs"] == 1
    assert result["summary"]["card_updates"] == 1
