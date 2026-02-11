# -*- coding: utf-8 -*-
from datetime import datetime, timedelta
import unittest

from ptcgp_auto_v2.services.gift_pairing_service import GiftPairingService


class TestGiftPairingService(unittest.TestCase):
    def test_is_account_past_cooldown_true(self):
        created_at = datetime.now() - timedelta(days=15)
        self.assertTrue(GiftPairingService.is_account_past_cooldown(created_at))

    def test_is_account_past_cooldown_false(self):
        created_at = datetime.now() - timedelta(days=3)
        self.assertFalse(GiftPairingService.is_account_past_cooldown(created_at))

    def test_is_account_past_cooldown_none(self):
        self.assertFalse(GiftPairingService.is_account_past_cooldown(None))

    def test_plan_missing_pairs_even_accounts(self):
        pairs = GiftPairingService.plan_missing_pairs(
            sorted_account_ids=[11, 9, 8, 7],
            existing_pair_map={},
        )
        self.assertEqual(pairs, [(11, 9), (8, 7)])

    def test_plan_missing_pairs_keep_existing_stable_relation(self):
        pairs = GiftPairingService.plan_missing_pairs(
            sorted_account_ids=[1, 2, 3, 4],
            existing_pair_map={1: 3, 3: 1},
        )
        self.assertEqual(pairs, [(2, 4)])

    def test_plan_missing_pairs_odd_accounts_leave_last_unpaired(self):
        pairs = GiftPairingService.plan_missing_pairs(
            sorted_account_ids=[1, 2, 3, 4, 5],
            existing_pair_map={},
        )
        self.assertEqual(pairs, [(1, 2), (3, 4)])


if __name__ == "__main__":
    unittest.main()
