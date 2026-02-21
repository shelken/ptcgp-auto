# -*- coding: utf-8 -*-
"""高稀有度保存与通知测试。"""

import unittest
from types import SimpleNamespace

from ptcgp_auto_v2.tasks.utils.high_rarity_saver import save_high_rarity_cards


class _FakeRepo:
    def __init__(self):
        self.calls = []

    def upsert(self, **kwargs):
        self.calls.append(kwargs)


class _FakeNotifier:
    def __init__(self):
        self.calls = []

    def notify_rare_card(self, **kwargs):
        self.calls.append(kwargs)


class TestHighRaritySaver(unittest.TestCase):
    def test_save_high_rarity_cards_saves_and_notifies_high_rarity_only(self):
        repo = _FakeRepo()
        notifier = _FakeNotifier()
        account = SimpleNamespace(id=1, nickname="tester")
        rows = [
            {
                "card_id": 101,
                "rarity": "SR",
                "confidence": 0.9,
                "hash_similarity": 0.8,
                "card_obj": SimpleNamespace(id=101, name="A", rarity="SR"),
            },
            {
                "card_id": 102,
                "rarity": "AR",
                "confidence": 0.8,
                "hash_similarity": 0.7,
                "card_obj": SimpleNamespace(id=102, name="B", rarity="AR"),
            },
            {
                "card_id": 103,
                "rarity": "C",
                "confidence": 0.7,
                "hash_similarity": 0.6,
                "card_obj": SimpleNamespace(id=103, name="C", rarity="C"),
            },
        ]

        save_high_rarity_cards(
            account_card_repo=repo,
            account_id=1,
            rows=rows,
            account=account,
            notifier=notifier,
            notify_message="得卡挑战获得稀有卡牌",
        )

        self.assertEqual(2, len(repo.calls))
        self.assertEqual(2, len(notifier.calls))
        self.assertEqual("SR", notifier.calls[0]["rarity"])
        self.assertEqual("AR", notifier.calls[1]["rarity"])
        self.assertEqual("得卡挑战获得稀有卡牌", notifier.calls[0]["message"])


if __name__ == "__main__":
    unittest.main()
