# -*- coding: utf-8 -*-

from types import SimpleNamespace

from sqlmodel import Session

from ptcgp_auto_v2.web.services.record_service import build_records_list_context


class _StrictPackCard:
    """严格卡牌对象：禁止动态增加 display_name 字段。"""

    __slots__ = ("position", "card_name", "rarity", "is_new", "card")

    def __init__(
        self, *, position: int, card_name: str, rarity: str, is_new: bool, card
    ):
        self.position = position
        self.card_name = card_name
        self.rarity = rarity
        self.is_new = is_new
        self.card = card


def test_build_records_list_context_should_not_mutate_pack_card_model(
    session: Session, monkeypatch
):
    """records 视图构建不应向 PackCard ORM 对象动态写入 display_name。"""

    localized_card = SimpleNamespace(
        data={"name": {"zh-CN": "皮卡丘中文"}}, name="Pikachu"
    )
    strict_pack_card = _StrictPackCard(
        position=1,
        card_name="Pikachu",
        rarity="R",
        is_new=True,
        card=localized_card,
    )
    fake_record = SimpleNamespace(
        cards=[strict_pack_card],
        account=SimpleNamespace(nickname="测试账号"),
        account_id=1,
        pack_code="A1",
        pack_type="daily_free",
        pack_name="Mewtwo",
        opened_at=SimpleNamespace(
            isoformat=lambda timespec=None: "2026-03-01T00:00:00"
        ),
    )

    monkeypatch.setattr(
        "ptcgp_auto_v2.web.services.record_service.fetch_records",
        lambda *_args, **_kwargs: ([fake_record], False),
    )
    monkeypatch.setattr(
        "ptcgp_auto_v2.web.services.record_service.fetch_pack_points_map",
        lambda *_args, **_kwargs: {},
    )

    class _FakeCardRepo:
        def get_all_sets(self):
            return [SimpleNamespace(code="A1", label_data='{"zh-CN":"A1系列中文"}')]

        def get_all_packs(self):
            return [SimpleNamespace(name="Mewtwo", label_data='{"zh-CN":"超梦包中文"}')]

    monkeypatch.setattr(
        "ptcgp_auto_v2.web.services.record_service.CardRepository",
        lambda: _FakeCardRepo(),
    )
    monkeypatch.setattr(
        "ptcgp_auto_v2.web.services.record_service.resolve_card_name_from_data",
        lambda *_args, **_kwargs: "皮卡丘中文",
    )

    context = build_records_list_context(session=session)

    assert context["items"][0]["cards"][0]["display_name"] == "皮卡丘中文"
    assert context["items"][0]["cards"][0]["card_name"] == "Pikachu"
