# -*- coding: utf-8 -*-
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
