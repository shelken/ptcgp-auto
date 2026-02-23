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
        self.upsert_set_calls = 0
        self.upsert_card_calls = 0
        self.clear_card_pack_calls = 0
        self.add_card_pack_calls: list[tuple[int, str]] = []
        self.upsert_pack_calls = 0

    def get_set_by_code(self, code: str):
        return None

    def get_card_by_set_and_number(self, set_code: str, number: int):
        return None

    def get_pack_by_name(self, name: str):
        return None

    def upsert_set(self, card_set):
        self.upsert_set_calls += 1
        return card_set

    def upsert_card(self, card):
        self.upsert_card_calls += 1
        return SimpleNamespace(id=1)

    def clear_card_packs(self, card_id: int):
        self.clear_card_pack_calls += 1

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
    """存在新增数据时，应输出新增系列/卡牌/卡包清单。"""
    module = _load_sync_module()
    caplog.set_level(logging.INFO, logger=module.logger.name)
    fake_repo = _FakeRepo()
    sets_data, cards_data, extra_map = _build_fake_remote_data()

    payload = module.build_sync_payload(fake_repo, sets_data, cards_data, extra_map)
    module.show_preview(payload.preview)

    assert "新增系列: 1" in caplog.text
    assert "新增卡牌: 1" in caplog.text
    assert "新增卡包: 1" in caplog.text
    assert "A1" in caplog.text
    assert "A1-001" in caplog.text
    assert "Pack A" in caplog.text


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
    assert fake_repo.clear_card_pack_calls == 1
    assert fake_repo.upsert_pack_calls == 1
    assert fake_repo.add_card_pack_calls == [(1, "Pack A")]
