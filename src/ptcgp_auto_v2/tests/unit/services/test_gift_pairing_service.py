# -*- coding: utf-8 -*-
"""GiftPairingService 行为测试。"""

from ptcgp_auto_v2.services import gift_pairing_service
from ptcgp_auto_v2.services.gift_pairing_service import GiftPairingService


class _FakeSession:
    def exec(self, statement):
        return self

    def all(self):
        return [(2, "2222", 1), (1, "1111", 0)]


def test_load_ranked_accounts_uses_caller_session(monkeypatch):
    """加载配对候选账号时必须复用调用方事务视图。"""

    def fail_get_session():
        raise AssertionError("不应在 _load_ranked_accounts 内创建新 Session")

    monkeypatch.setattr(gift_pairing_service, "get_session", fail_get_session, raising=False)

    ranked_accounts = GiftPairingService._load_ranked_accounts(_FakeSession())

    assert ranked_accounts == [
        {"account_id": 2, "friend_id": "2222", "rarity_score": 1},
        {"account_id": 1, "friend_id": "1111", "rarity_score": 0},
    ]
