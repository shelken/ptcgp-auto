# -*- coding: utf-8 -*-

import importlib.util
import logging
import sys
from pathlib import Path
from types import SimpleNamespace


def _load_sync_module():
    """按文件路径加载同步脚本模块，避免依赖 package 初始化。"""
    script_path = (
        Path(__file__).resolve().parents[3]
        / "src"
        / "ptcgp_auto_v2"
        / "scripts"
        / "sync_metadata.py"
    )
    spec = importlib.util.spec_from_file_location("sync_metadata_script", script_path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class _FakeRepo:
    """仓储替身：记录读写调用，避免真实数据库依赖。"""

    def __init__(self):
        self.existing_sets: dict[str, SimpleNamespace] = {}
        self.existing_cards: dict[tuple[str, int], SimpleNamespace] = {}
        self.existing_packs: dict[str, SimpleNamespace] = {}
        self.card_pack_names: dict[int, list[str]] = {}
        self.upsert_set_calls = 0
        self.upsert_card_calls = 0
        self.remove_card_pack_calls: list[tuple[int, str]] = []
        self.add_card_pack_calls: list[tuple[int, str]] = []
        self.upsert_pack_calls = 0

    def get_set_by_code(self, code: str):
        return self.existing_sets.get(code)

    def get_card_by_set_and_number(self, set_code: str, number: int):
        return self.existing_cards.get((set_code, number))

    def get_pack_by_name(self, name: str):
        return self.existing_packs.get(name)

    def get_card_pack_names(self, card_id: int):
        return self.card_pack_names.get(card_id, [])

    def upsert_set(self, card_set):
        self.upsert_set_calls += 1
        return card_set

    def upsert_card(self, card):
        self.upsert_card_calls += 1
        return SimpleNamespace(id=1)

    def remove_card_pack(self, card_id: int, pack_name: str):
        self.remove_card_pack_calls.append((card_id, pack_name))

    def add_card_pack(self, card_id: int, pack_name: str):
        self.add_card_pack_calls.append((card_id, pack_name))

    def upsert_pack_safe(self, pack):
        self.upsert_pack_calls += 1
        return pack


def _build_fake_remote_data():
    """构造最小可用远端数据，覆盖新增系列/卡牌/卡包。"""
    sets_data = {
        "A": [
            {
                "code": "A1",
                "name": {"en": "Set A1"},
                "releaseDate": "2024-01-01",
                "count": 1,
            }
        ]
    }
    cards_data = [
        {
            "set": "A1",
            "number": 1,
            "name": "Card 1",
            "rarity": "C",
            "image": "https://example.com/card.png",
            "packs": ["Pack A"],
        }
    ]
    extra_map = {("A1", 1): {"element": "Grass", "health": "60", "retreatCost": "1"}}
    return sets_data, cards_data, extra_map


def test_show_preview_should_print_new_items(caplog):
    """存在新增数据时，应输出新增数量与空的更新/删除明细。"""
    module = _load_sync_module()
    caplog.set_level(logging.INFO, logger=module.logger.name)
    fake_repo = _FakeRepo()
    sets_data, cards_data, extra_map = _build_fake_remote_data()

    payload = module.build_sync_payload(fake_repo, sets_data, cards_data, extra_map)
    module.show_preview(payload.preview)

    assert "新增系列: 1" in caplog.text
    assert "新增卡牌: 1" in caplog.text
    assert "新增卡包: 1" in caplog.text
    assert "更新明细: 0" in caplog.text
    assert "删除明细: 0" in caplog.text


def test_sync_metadata_should_not_write_when_input_is_not_y(monkeypatch):
    """输入非 y 时应取消写入，且不调用任何写库方法。"""
    module = _load_sync_module()
    fake_repo = _FakeRepo()
    sets_data, cards_data, extra_map = _build_fake_remote_data()

    monkeypatch.setattr(module, "CardRepository", lambda: fake_repo)
    monkeypatch.setattr(
        module,
        "fetch_remote_metadata",
        lambda: (sets_data, cards_data, extra_map),
    )

    result = module.sync_metadata(input_fn=lambda _prompt: "n")

    assert result is False
    assert fake_repo.upsert_set_calls == 0
    assert fake_repo.upsert_card_calls == 0
    assert fake_repo.upsert_pack_calls == 0
    assert fake_repo.add_card_pack_calls == []
    assert fake_repo.remove_card_pack_calls == []


def test_sync_metadata_should_write_when_input_is_y(monkeypatch):
    """输入 y 时应执行写库，调用系列/卡牌/卡包写入流程。"""
    module = _load_sync_module()
    fake_repo = _FakeRepo()
    sets_data, cards_data, extra_map = _build_fake_remote_data()

    monkeypatch.setattr(module, "CardRepository", lambda: fake_repo)
    monkeypatch.setattr(
        module,
        "fetch_remote_metadata",
        lambda: (sets_data, cards_data, extra_map),
    )

    result = module.sync_metadata(input_fn=lambda _prompt: "y")

    assert result is True
    assert fake_repo.upsert_set_calls == 1
    assert fake_repo.upsert_card_calls == 1
    assert fake_repo.remove_card_pack_calls == []
    assert fake_repo.upsert_pack_calls == 1
    assert fake_repo.add_card_pack_calls == [(1, "Pack A")]


def test_sync_metadata_should_skip_write_when_card_and_pack_unchanged(monkeypatch):
    """卡牌字段和卡包关联完全一致时，不应执行写入。"""
    module = _load_sync_module()
    fake_repo = _FakeRepo()
    sets_data, cards_data, extra_map = _build_fake_remote_data()

    fake_repo.existing_sets["A1"] = SimpleNamespace(
        code="A1",
        name="Set A1",
        release_date="2024-01-01",
        total_cards=1,
        label_data='{"en":"Set A1"}',
    )
    fake_repo.existing_cards[("A1", 1)] = SimpleNamespace(
        id=99,
        set_code="A1",
        number=1,
        name="Card 1",
        rarity="C",
        image_url="https://example.com/card.png",
        element="Grass",
        type=None,
        stage=None,
        health=60,
        weakness=None,
        retreat_cost=1,
        data='{"set":"A1","number":1,"name":"Card 1","rarity":"C","image":"https://example.com/card.png","packs":["Pack A"]}',
    )
    fake_repo.card_pack_names[99] = ["Pack A"]
    fake_repo.existing_packs["Pack A"] = SimpleNamespace(name="Pack A", set_code="A1")

    monkeypatch.setattr(module, "CardRepository", lambda: fake_repo)
    monkeypatch.setattr(
        module,
        "fetch_remote_metadata",
        lambda: (sets_data, cards_data, extra_map),
    )

    result = module.sync_metadata(input_fn=lambda _prompt: "y")

    assert result is True
    assert fake_repo.upsert_set_calls == 0
    assert fake_repo.upsert_card_calls == 0
    assert fake_repo.remove_card_pack_calls == []
    assert fake_repo.upsert_pack_calls == 0
    assert fake_repo.add_card_pack_calls == []


def test_build_sync_payload_should_preserve_existing_zh_label():
    """已有系列标签包含中文时，远端缺少 zh 也不能覆盖已有中文。"""
    module = _load_sync_module()
    fake_repo = _FakeRepo()
    fake_repo.existing_sets["A2"] = SimpleNamespace(
        code="A2",
        name="Old EN",
        release_date="2024-02-01",
        total_cards=1,
        label_data='{"en":"Old EN","zh":"時空激鬥"}',
    )

    sets_data = {
        "A": [
            {
                "code": "A2",
                "name": {"en": "Space-Time Smackdown"},
                "releaseDate": "2024-02-01",
                "count": 1,
            }
        ]
    }

    payload = module.build_sync_payload(fake_repo, sets_data, [], {})

    assert payload.preview.new_set_count == 0
    assert len(payload.sets_to_upsert) == 1
    assert (
        payload.sets_to_upsert[0].label_data
        == '{"en": "Space-Time Smackdown", "zh": "時空激鬥"}'
    )


def test_show_preview_should_list_update_and_delete_rows(caplog):
    """更新与删除应逐条输出，且精确到字段。"""
    module = _load_sync_module()
    caplog.set_level(logging.INFO, logger=module.logger.name)
    fake_repo = _FakeRepo()

    fake_repo.existing_sets["A1"] = SimpleNamespace(
        code="A1",
        name="Old Set",
        release_date="2024-01-01",
        total_cards=1,
        label_data='{"en":"Old Set"}',
    )
    fake_repo.existing_cards[("A1", 1)] = SimpleNamespace(
        id=10,
        set_code="A1",
        number=1,
        name="Old Card",
        rarity="C",
        image_url="old.png",
        element="Grass",
        type=None,
        stage=None,
        health=60,
        weakness=None,
        retreat_cost=1,
        data='{"name":"Old Card"}',
    )
    fake_repo.card_pack_names[10] = ["Pack Old", "Pack Keep"]

    sets_data = {
        "A": [
            {
                "code": "A1",
                "name": {"en": "New Set"},
                "releaseDate": "2024-01-01",
                "count": 1,
            }
        ]
    }
    cards_data = [
        {
            "set": "A1",
            "number": 1,
            "name": "New Card",
            "rarity": "C",
            "image": "new.png",
            "packs": ["Pack Keep", "Pack New"],
        }
    ]

    payload = module.build_sync_payload(fake_repo, sets_data, cards_data, {})
    module.show_preview(payload.preview)

    assert "更新明细:" in caplog.text
    assert "[card_sets] A1 字段 name: Old Set -> New Set" in caplog.text
    assert "[cards] A1-001 字段 name: Old Card -> New Card" in caplog.text
    assert "[cards] A1-001 字段 image_url: old.png -> new.png" in caplog.text
    assert "删除明细:" in caplog.text
    assert "[card_packs] A1-001 (删除关联 pack_name=Pack Old)" in caplog.text
