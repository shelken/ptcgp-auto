# -*- coding: utf-8 -*-

from datetime import datetime
from unittest.mock import patch

import pytest
from sqlmodel import Session, SQLModel, create_engine

from ptcgp_auto_v2.db.models import Account, ExchangeCardRequest
from ptcgp_auto_v2.web.services.exchange_card_service import build_exchange_card_context


@pytest.fixture(name="engine")
def engine_fixture():
    """创建内存数据库引擎。"""
    engine = create_engine("sqlite:///:memory:")
    SQLModel.metadata.create_all(engine)
    return engine


def test_management_exchange_page_renders_requests_and_actions(engine):
    """管理页应展示交换请求列表并提供取消操作。"""
    with Session(engine) as session:
        from_account = Account(game_id="g-1", nickname="from-user", friend_id="1111")
        to_account = Account(game_id="g-2", nickname="to-user", friend_id="2222")
        session.add(from_account)
        session.add(to_account)
        session.commit()
        assert from_account.id is not None
        assert to_account.id is not None

        session.add(
            ExchangeCardRequest(
                from_account_id=from_account.id,
                to_account_id=to_account.id,
                to_friend_id=to_account.friend_id or "",
                target_card_id=100,
                target_card_rarity="RR",
                status="sending",
                created_at=datetime.now(),
                updated_at=datetime.now(),
            )
        )
        session.commit()

        context = build_exchange_card_context(session=session, lang="zh_CN")

    assert context["requests"]
    assert context["requests"][0]["can_cancel"] is True
