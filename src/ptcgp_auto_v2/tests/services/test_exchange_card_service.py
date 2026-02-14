# -*- coding: utf-8 -*-
from datetime import datetime, timedelta
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from sqlmodel import SQLModel, create_engine

from ptcgp_auto_v2.db.repositories.exchange_card_request_repository import (
    ExchangeCardRequestRepository,
)
from ptcgp_auto_v2.services.exchange_card_service import ExchangeCardService


@pytest.fixture(name="engine")
def engine_fixture():
    """创建内存数据库引擎。"""
    engine = create_engine("sqlite:///:memory:")
    SQLModel.metadata.create_all(engine)
    return engine


@pytest.fixture(name="mock_get_engine")
def mock_get_engine_fixture(engine):
    """将仓储层引擎替换为测试内存引擎。"""
    with patch(
        "ptcgp_auto_v2.db.repositories.exchange_card_request_repository.get_engine",
        return_value=engine,
    ):
        yield


def test_one_account_only_one_active_exchange_request(engine, mock_get_engine):
    """同一账号在非 completed/failed/canceled 状态下只能有一条活跃请求。"""
    repo = ExchangeCardRequestRepository()

    first = repo.create(
        from_account_id=101,
        to_account_id=202,
        to_friend_id="123456789",
        target_card_id=3001,
        target_card_rarity="RR",
        status="sending",
    )
    assert first is not None

    second = repo.create(
        from_account_id=101,
        to_account_id=303,
        to_friend_id="987654321",
        target_card_id=4001,
        target_card_rarity="SR",
        status="sending",
    )
    assert second is None


def test_create_request_rejects_im_and_ur_rarity():
    """IM/UR 稀有度在服务层必须被拒绝。"""
    with patch(
        "ptcgp_auto_v2.services.exchange_card_service.ExchangeCardRequestRepository"
    ) as repo_cls:
        created = ExchangeCardService.create_request(
            from_account_id=101,
            to_account_id=202,
            to_friend_id="123456789",
            target_card_id=3001,
            target_card_rarity="IM",
        )

        assert created is None
        repo_cls.return_value.create.assert_not_called()


def test_has_active_request_returns_true_for_sending_or_sended(engine, mock_get_engine):
    """sending/sended 状态应被识别为活跃请求。"""
    repo = ExchangeCardRequestRepository()
    created = repo.create(
        from_account_id=301,
        to_account_id=302,
        to_friend_id="1111222233334444",
        target_card_id=7001,
        target_card_rarity="R",
        status="sending",
    )
    assert created is not None
    assert repo.has_active_request(301) is True

    created.status = "sended"
    repo.update(created)
    assert repo.has_active_request(301) is True

    created.status = "completed"
    repo.update(created)
    assert repo.has_active_request(301) is False


def test_list_due_sended_requests_only_returns_due_rows(engine, mock_get_engine):
    """仅返回 next_check_at <= now 的 sended 请求。"""
    repo = ExchangeCardRequestRepository()
    now = datetime.now()

    due = repo.create(
        from_account_id=401,
        to_account_id=402,
        to_friend_id="1111000011110000",
        target_card_id=7101,
        target_card_rarity="RR",
        status="sended",
    )
    future = repo.create(
        from_account_id=403,
        to_account_id=404,
        to_friend_id="2222000022220000",
        target_card_id=7102,
        target_card_rarity="RR",
        status="sended",
    )
    assert due is not None
    assert future is not None

    due.next_check_at = now - timedelta(minutes=1)
    future.next_check_at = now + timedelta(minutes=10)
    repo.update(due)
    repo.update(future)

    rows = repo.list_due_sended_requests(now)
    assert [row.from_account_id for row in rows] == [401]


def test_create_request_rejects_active_account_request():
    """服务层应拒绝已存在活跃请求的账号再次创建请求。"""
    with patch(
        "ptcgp_auto_v2.services.exchange_card_service.ExchangeCardRequestRepository"
    ) as repo_cls:
        repo = repo_cls.return_value
        repo.has_active_request.return_value = True

        created = ExchangeCardService.create_request(
            from_account_id=601,
            to_account_id=602,
            to_friend_id="1234567890123456",
            target_card_id=8001,
            target_card_rarity="R",
        )

        assert created is None
        repo.create.assert_not_called()


def test_create_request_sets_expire_at_when_created():
    """创建请求后应写入过期时间窗口。"""
    with patch(
        "ptcgp_auto_v2.services.exchange_card_service.ExchangeCardRequestRepository"
    ) as repo_cls:
        repo = repo_cls.return_value
        repo.has_active_request.return_value = False

        row = SimpleNamespace(expire_at=None)
        repo.create.return_value = row
        repo.update.return_value = row

        created = ExchangeCardService.create_request(
            from_account_id=611,
            to_account_id=612,
            to_friend_id="1234567890123456",
            target_card_id=8101,
            target_card_rarity="RR",
        )

        assert created is row
        assert row.expire_at is not None
        repo.update.assert_called_once_with(row)
