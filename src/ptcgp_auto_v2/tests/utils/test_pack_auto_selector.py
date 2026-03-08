# -*- coding: utf-8 -*-
"""
自动选包策略测试
"""

import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

src_dir = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(src_dir))

from ptcgp_auto_v2.utils import pack_auto_selector
from ptcgp_auto_v2.utils.pack_auto_selector import select_pack_for_account


class FakeCardRepo:
    def __init__(self, packs, card_sets, progress_map=None):
        self._packs = packs
        self._card_sets = card_sets
        self._progress_map = progress_map or {}

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

    def get_pack_target_rarity_progress(self, pack_names, target_rarities):
        return {
            pack_name: self._progress_map.get(
                pack_name,
                {"owned_target": 0, "total_target": 0},
            )
            for pack_name in pack_names
        }


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
    def setUp(self):
        pack_auto_selector._HRW_WEEKLY_CACHE.clear()

    def test_hrw_effective_params_follow_aggressiveness_curve(self):
        with patch.object(pack_auto_selector, "PACK_AUTO_HRW_AGGRESSIVENESS", 0.0):
            effective_scale, effective_weight_max, effective_epsilon = (
                pack_auto_selector._build_hrw_effective_params()
            )
            self.assertEqual(effective_scale, 0.0)
            self.assertEqual(effective_weight_max, 1.0)
            self.assertEqual(effective_epsilon, 0.0)

        with patch.object(pack_auto_selector, "PACK_AUTO_HRW_AGGRESSIVENESS", 0.5):
            effective_scale, effective_weight_max, effective_epsilon = (
                pack_auto_selector._build_hrw_effective_params()
            )
            self.assertEqual(effective_scale, 1.5)
            self.assertAlmostEqual(effective_weight_max, 4.4816890703380645)
            self.assertEqual(effective_epsilon, 1.0)

        with patch.object(pack_auto_selector, "PACK_AUTO_HRW_AGGRESSIVENESS", 1.0):
            effective_scale, effective_weight_max, effective_epsilon = (
                pack_auto_selector._build_hrw_effective_params()
            )
            self.assertEqual(effective_scale, 6.0)
            self.assertAlmostEqual(effective_weight_max, 403.4287934927351)
            self.assertEqual(effective_epsilon, 4.0)

    def test_hrw_effective_params_reject_invalid_aggressiveness(self):
        with patch.object(pack_auto_selector, "PACK_AUTO_HRW_AGGRESSIVENESS", 1.1):
            with self.assertRaisesRegex(ValueError, "PACK_AUTO_HRW_AGGRESSIVENESS"):
                pack_auto_selector._build_hrw_effective_params()

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

    def test_hrw_progress_balance_is_stable(self):
        packs = [
            SimpleNamespace(set_code="A1", name="Pikachu"),
            SimpleNamespace(set_code="A2", name="Charizard"),
        ]
        repo = FakeCardRepo(packs, [])
        record_repo = FakeRecordRepo()
        account = FakeAccount(account_id=42)

        first = select_pack_for_account(
            account=account,
            strategy="hrw_progress_balance",
            card_repo=repo,
            record_repo=record_repo,
            exclude_set_codes=[],
        )
        second = select_pack_for_account(
            account=account,
            strategy="hrw_progress_balance",
            card_repo=repo,
            record_repo=record_repo,
            exclude_set_codes=[],
        )

        self.assertEqual(first, second)

    def test_hrw_progress_balance_prefers_low_progress_pack(self):
        packs = [
            SimpleNamespace(set_code="A1", name="Pikachu"),
            SimpleNamespace(set_code="A2", name="Charizard"),
        ]
        progress_map = {
            "Pikachu": {"owned_target": 10, "total_target": 10},
            "Charizard": {"owned_target": 0, "total_target": 10},
        }
        repo = FakeCardRepo(packs, [], progress_map=progress_map)
        record_repo = FakeRecordRepo()
        account = FakeAccount(account_id=42)

        with (
            patch(
                "ptcgp_auto_v2.utils.pack_auto_selector._load_all_account_keys",
                return_value=["id:42"],
            ),
            patch(
                "ptcgp_auto_v2.utils.pack_auto_selector._build_seed_candidates",
                return_value=["seed-test"],
            ),
            patch(
                "ptcgp_auto_v2.utils.pack_auto_selector._hash_to_unit",
                return_value=0.5,
            ),
        ):
            result = select_pack_for_account(
                account=account,
                strategy="hrw_progress_balance",
                card_repo=repo,
                record_repo=record_repo,
                exclude_set_codes=[],
            )

        self.assertIsNotNone(result)
        self.assertEqual(result["pack_code"], "A2")
        self.assertEqual(result["booster_name"], "Charizard")

    def test_hrw_progress_balance_seed_uses_game_biz_date(self):
        packs = [SimpleNamespace(set_code="A1", name="Pikachu")]
        progress_map = {"Pikachu": {"owned_target": 0, "total_target": 10}}
        repo = FakeCardRepo(packs, [], progress_map=progress_map)
        record_repo = FakeRecordRepo()
        account = FakeAccount(account_id=1)

        with (
            patch(
                "ptcgp_auto_v2.utils.pack_auto_selector.get_game_biz_date_str",
                return_value="2026-02-24",
            ),
            patch(
                "ptcgp_auto_v2.utils.pack_auto_selector._load_all_account_keys",
                return_value=["id:1"],
            ),
            patch(
                "ptcgp_auto_v2.utils.pack_auto_selector._build_seed_candidates",
                return_value=["rarity-gap-auto-39|2026-W09"],
            ),
            patch(
                "ptcgp_auto_v2.utils.pack_auto_selector._hash_to_unit",
                return_value=0.5,
            ) as hash_mock,
        ):
            result = select_pack_for_account(
                account=account,
                strategy="hrw_progress_balance",
                card_repo=repo,
                record_repo=record_repo,
                exclude_set_codes=[],
            )

        self.assertIsNotNone(result)
        hash_mock.assert_called_with("id:1|A1/Pikachu|rarity-gap-auto-39|2026-W09")

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
