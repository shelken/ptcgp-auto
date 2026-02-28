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
