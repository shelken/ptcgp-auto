# -*- coding: utf-8 -*-
"""
卡牌名称解析工具测试
"""

import sys
import unittest
from pathlib import Path
from types import SimpleNamespace

src_dir = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(src_dir))

from ptcgp_auto_v2.utils.card_name_resolver import resolve_card_name


class FakeRepo:
    def __init__(self, data):
        self._data = data

    def get_card_by_set_and_number(self, set_code, card_number):
        name = self._data.get((set_code, card_number))
        if name is None:
            return None
        return SimpleNamespace(name=name)


class TestResolveCardName(unittest.TestCase):
    def test_returns_name_when_found(self):
        repo = FakeRepo({("B2", 28): "皮卡丘"})
        self.assertEqual(resolve_card_name(repo, "B2", 28), "皮卡丘")

    def test_returns_none_when_missing(self):
        repo = FakeRepo({})
        self.assertIsNone(resolve_card_name(repo, "B2", 28))


if __name__ == "__main__":
    unittest.main()
