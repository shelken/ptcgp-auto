# -*- coding: utf-8 -*-
"""
自动选包策略测试
"""

import sys
import unittest
from pathlib import Path
from types import SimpleNamespace

src_dir = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(src_dir))

from ptcgp_auto_v2.utils.pack_auto_selector import select_pack_for_account


class FakeCardRepo:
    def __init__(self, packs, card_sets):
        self._packs = packs
        self._card_sets = card_sets

    def get_packs_by_set_prefixes(self, prefixes, exclude_set_codes):
        exclude = {code.upper() for code in exclude_set_codes}
        result = []
        for pack in self._packs:
            if not pack.set_code:
                continue
            if any(pack.set_code.startswith(prefix) for prefix in prefixes):
                if pack.set_code.upper() in exclude:
                    continue
                result.append(pack)
        return result

    def get_all_sets(self):
        return self._card_sets


class FakeRecordRepo:
    def __init__(self, counts=None):
        self._counts = counts or {}

    def get_pack_usage_counts(self, pack_keys):
        return {key: self._counts.get(key, 0) for key in pack_keys}


class FakeAccount:
    def __init__(self, account_id=None, game_id=None, display_name=None, nickname=None):
        self.id = account_id
        self.game_id = game_id
        self.display_name = display_name
        self.nickname = nickname


class TestPackAutoSelector(unittest.TestCase):
    def test_latest_strategy_picks_newest_set(self):
        packs = [
            SimpleNamespace(set_code="A1", name="Pikachu"),
            SimpleNamespace(set_code="A2", name="Charizard"),
        ]
        card_sets = [
            SimpleNamespace(code="A1", release_date="2024-01-01"),
            SimpleNamespace(code="A2", release_date="2025-01-01"),
        ]
        repo = FakeCardRepo(packs, card_sets)
        record_repo = FakeRecordRepo()
        account = FakeAccount(account_id=1)

        result = select_pack_for_account(
            account=account,
            strategy="latest",
            card_repo=repo,
            record_repo=record_repo,
            exclude_set_codes=[],
        )

        self.assertIsNotNone(result)
        self.assertEqual(result["pack_code"], "A2")
        self.assertEqual(result["booster_name"], "Charizard")

    def test_hash_balance_is_stable(self):
        packs = [
            SimpleNamespace(set_code="A1", name="Pikachu"),
            SimpleNamespace(set_code="A2", name="Charizard"),
        ]
        repo = FakeCardRepo(packs, [])
        record_repo = FakeRecordRepo()
        account = FakeAccount(account_id=42)

        first = select_pack_for_account(
            account=account,
            strategy="hash_balance",
            card_repo=repo,
            record_repo=record_repo,
            exclude_set_codes=[],
        )
        second = select_pack_for_account(
            account=account,
            strategy="hash_balance",
            card_repo=repo,
            record_repo=record_repo,
            exclude_set_codes=[],
        )

        self.assertEqual(first, second)

    def test_least_used_prefers_lowest_count(self):
        packs = [
            SimpleNamespace(set_code="A1", name="Pikachu"),
            SimpleNamespace(set_code="A2", name="Charizard"),
        ]
        counts = {
            ("A1", "Pikachu"): 5,
            ("A2", "Charizard"): 1,
        }
        repo = FakeCardRepo(packs, [])
        record_repo = FakeRecordRepo(counts)
        account = FakeAccount(account_id=7)

        result = select_pack_for_account(
            account=account,
            strategy="least_used",
            card_repo=repo,
            record_repo=record_repo,
            exclude_set_codes=[],
        )

        self.assertIsNotNone(result)
        self.assertEqual(result["pack_code"], "A2")
        self.assertEqual(result["booster_name"], "Charizard")


if __name__ == "__main__":
    unittest.main()
