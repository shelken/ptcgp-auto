# -*- coding: utf-8 -*-
"""metadata_service 视图层测试。"""

from __future__ import annotations

import json

from sqlmodel import Session, SQLModel

from ptcgp_auto_v2.db.models import Card, CardPack, CardSet, Pack
from ptcgp_auto_v2.web.services import metadata_service
from ptcgp_auto_v2.web.utils.i18n import set_lang_context


def test_build_metadata_context_prefers_zh_labels(monkeypatch, memory_engine):
    """中文语言下应优先展示 zh 标签。"""
    monkeypatch.setattr("ptcgp_auto_v2.db.engine.get_engine", lambda: memory_engine)

    SQLModel.metadata.create_all(memory_engine)
    with Session(memory_engine) as session:
        session.add(
            CardSet(
                code="A1",
                name="Set EN",
                release_date="2024-01-01",
                total_cards=1,
                label_data=json.dumps(
                    {"en": "Set EN", "zh": "系列中文"}, ensure_ascii=False
                ),
            )
        )
        session.add(
            Pack(
                name="Pack EN",
                set_code="A1",
                label_data=json.dumps(
                    {"en": "Pack EN", "zh": "卡包中文"}, ensure_ascii=False
                ),
            )
        )
        card = Card(
            set_code="A1",
            number=1,
            name="Card EN",
            rarity="C",
            image_url="a.webp",
            data=json.dumps(
                {
                    "name": "Card EN",
                    "localized_name": {"en": "Card EN", "zh": "卡牌中文"},
                },
                ensure_ascii=False,
            ),
        )
        session.add(card)
        session.commit()
        session.refresh(card)
        session.add(CardPack(card_id=card.id or 0, pack_name="Pack EN"))
        session.commit()

    monkeypatch.setattr(
        metadata_service,
        "build_default_check_context",
        lambda: {"local": {}, "flibustier": {}, "poke52": {}},
    )

    set_lang_context("zh_CN")
    context = metadata_service.build_metadata_context(
        selected_node_type="pack",
        selected_node_id="Pack EN",
        selected_set_code="A1",
        selected_pack_name="Pack EN",
    )

    assert context["sets"][0]["label_dict"].get("zh") == "系列中文"

    assert context["sets"][0]["display_name"] == "系列中文"
    assert context["packs_by_set"]["A1"][0]["display_name"] == "卡包中文"
    assert context["selected_pack_cards"][0]["display_name"] == "卡牌中文"


def test_build_metadata_context_prefers_en_labels(monkeypatch, memory_engine):
    """英文语言下应优先展示 en 标签。"""
    monkeypatch.setattr("ptcgp_auto_v2.db.engine.get_engine", lambda: memory_engine)
    SQLModel.metadata.create_all(memory_engine)

    with Session(memory_engine) as session:
        session.add(
            CardSet(
                code="B1",
                name="Set Fallback",
                release_date="2024-01-01",
                total_cards=1,
                label_data=json.dumps(
                    {"en": "Set English", "zh": "系列中文"}, ensure_ascii=False
                ),
            )
        )
        session.commit()

    monkeypatch.setattr(
        metadata_service,
        "build_default_check_context",
        lambda: {"local": {}, "flibustier": {}, "poke52": {}},
    )

    set_lang_context("en")
    context = metadata_service.build_metadata_context()
    assert context["sets"][0]["display_name"] == "Set English"


def test_build_metadata_context_keeps_ui_state_fields(monkeypatch, memory_engine):
    """上下文应包含自动刷新所需状态字段。"""
    monkeypatch.setattr("ptcgp_auto_v2.db.engine.get_engine", lambda: memory_engine)
    SQLModel.metadata.create_all(memory_engine)

    with Session(memory_engine) as session:
        session.add(
            CardSet(
                code="A1",
                name="A1",
                release_date="2024-01-01",
                total_cards=1,
                label_data="{}",
            )
        )
        session.commit()

    monkeypatch.setattr(
        metadata_service,
        "build_default_check_context",
        lambda: {"local": {}, "flibustier": {}, "poke52": {}},
    )

    set_lang_context("zh_CN")
    context = metadata_service.build_metadata_context(
        ui_step=2,
        selected_node_type="set",
        selected_node_id="A1",
        selected_set_code="A1",
        selected_pack_name="",
    )

    assert context["ui_step"] == 2
    assert context["selected_node_type"] == "set"
    assert context["selected_node_id"] == "A1"


def test_resolve_sync_request_update_data_keeps_scope() -> None:
    """更新数据动作应映射到 flibustier + supplement，且保留节点范围。"""
    result = metadata_service.resolve_sync_request(
        node_type="pack",
        node_id="PackA",
        action="update_data_supplement",
    )
    assert result["source"] == "flibustier"
    assert result["mode"] == "supplement"
    assert result["scope_level"] == "pack"
    assert result["scope_value"] == "PackA"


def test_resolve_sync_request_update_chinese_uses_52poke() -> None:
    """更新中文动作应仅走 52poke supplement。"""
    result = metadata_service.resolve_sync_request(
        node_type="set",
        node_id="A1",
        action="update_chinese_supplement",
    )
    assert result["source"] == "52poke"
    assert result["mode"] == "supplement"
    assert result["scope_level"] == "set"
    assert result["scope_value"] == "A1"


def test_resolve_sync_request_update_new_series_only_all_scope() -> None:
    """更新新系列仅允许根节点范围。"""
    result = metadata_service.resolve_sync_request(
        node_type="root",
        node_id="all",
        action="update_new_series",
    )
    assert result["source"] == "flibustier"
    assert result["mode"] == "supplement"
    assert result["scope_level"] == "all"
    assert result["scope_value"] is None

    try:
        metadata_service.resolve_sync_request(
            node_type="pack",
            node_id="PackA",
            action="update_new_series",
        )
        assert False, "预期 update_new_series 在非 root 下抛错"
    except ValueError as exc:
        assert "仅支持根节点" in str(exc)


def test_resolve_sync_request_force_modes() -> None:
    """覆盖动作应映射到 force 模式。"""
    data_result = metadata_service.resolve_sync_request(
        node_type="set",
        node_id="A1",
        action="update_data_force",
    )
    zh_result = metadata_service.resolve_sync_request(
        node_type="set",
        node_id="A1",
        action="update_chinese_force",
    )
    assert data_result["mode"] == "force"
    assert zh_result["mode"] == "force"
