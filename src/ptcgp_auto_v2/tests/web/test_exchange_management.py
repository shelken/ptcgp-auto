# -*- coding: utf-8 -*-

from datetime import datetime
from unittest.mock import patch

import pytest
from sqlmodel import Session, SQLModel, create_engine

from ptcgp_auto_v2.db.models import Account, ExchangeCardRequest
from ptcgp_auto_v2.web.services.exchange_card_service import (
    build_exchange_card_context,
    cancel_exchange_request,
)


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


def test_cancel_sended_request_sets_cancel_intent_and_wakes_task():
    """sended 取消应写取消意图并唤醒 exchange_cards。"""
    request = ExchangeCardRequest(
        id=99,
        from_account_id=1001,
        to_account_id=1002,
        to_friend_id="1234567890123456",
        target_card_id=1,
        target_card_rarity="R",
        status="sended",
        created_at=datetime.now(),
        updated_at=datetime.now(),
    )

    with (
        patch(
            "ptcgp_auto_v2.web.services.exchange_card_service.ExchangeCardRequestRepository"
        ) as repo_cls,
        patch(
            "ptcgp_auto_v2.web.services.exchange_card_service.TaskInstanceRepository"
        ) as task_repo_cls,
    ):
        repo = repo_cls.return_value
        repo.get_by_id.return_value = request
        repo.update.return_value = request

        ok = cancel_exchange_request(99, reason="manual_cancel")

        assert ok is True
        assert request.status == "sended"
        assert request.cancel_reason == "manual_cancel"
        task_repo_cls.return_value.ensure_pending.assert_called_once_with(
            account_id=1001,
            task_type="exchange_cards",
            reset_type="once",
        )
