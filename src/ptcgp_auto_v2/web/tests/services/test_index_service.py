# -*- coding: utf-8 -*-

from sqlmodel import Session

from ptcgp_auto_v2.db.models import CardSet, Pack
from ptcgp_auto_v2.web.services.index_service import build_index_context
from ptcgp_auto_v2.web.utils.i18n import set_lang_context


def test_build_index_context_prefers_localized_set_and_pack_names(session: Session):
    """拥有卡牌筛选的系列/子包应优先显示当前语言本地化名称。"""
    session.add(
        CardSet(
            code="A1",
            name="Set EN",
            label_data='{"zh":"系列中文"}',
        )
    )
    session.add(
        Pack(
            name="Mewtwo",
            set_code="A1",
            label_data='{"zh":"超梦子包"}',
        )
    )
    session.commit()

    set_lang_context("zh_CN")
    context = build_index_context(session)

    set_item = next(item for item in context["card_sets"] if item["code"] == "A1")
    pack_item = next(item for item in context["packs"] if item["name"] == "Mewtwo")

    assert set_item["display_name"] == "系列中文"
    assert pack_item["display_name"] == "超梦子包"
