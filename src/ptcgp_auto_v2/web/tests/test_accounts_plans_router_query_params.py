# -*- coding: utf-8 -*-
"""账号与计划路由参数解析回归测试。"""

import pytest
from sqlalchemy.pool import StaticPool
from sqlmodel import SQLModel, Session, create_engine

import ptcgp_auto_v2.db.models  # noqa: F401
from ptcgp_auto_v2.db.models.account import Account
from ptcgp_auto_v2.web.routers.react_api_accounts_plans import (
    _build_basic_list_query_params,
    _parse_account_ids_param,
)
from ptcgp_auto_v2.web.services import account_service


@pytest.fixture
def session() -> Session:
    """为每个用例准备独立内存数据库。"""
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)

    with Session(engine) as session:
        yield session

    engine.dispose()


def _seed_pack_accounts(session: Session) -> None:
    """准备自动选包接口所需的最小账号样本。"""
    session.add_all(
        [
            Account(id=1, game_id="game-ash", nickname="Ash", friend_id="1111000011110000"),
            Account(id=2, game_id="game-misty", nickname="Misty", friend_id="2222000022220000"),
        ]
    )
    session.commit()


def test_build_basic_list_query_params_normalizes_basic_fields() -> None:
    params = _build_basic_list_query_params(
        {
            "q": " ash ",
            "sort_by": "nickname",
            "sort_order": "desc",
            "page": "-3",
            "page_size": "999",
        },
        default_sort_by="id",
        default_sort_order="asc",
        default_page_size=10,
    )

    assert params == {
        "q": " ash ",
        "sort_by": "nickname",
        "sort_order": "desc",
        "page": 0,
        "page_size": 100,
    }


def test_build_basic_list_query_params_uses_defaults() -> None:
    params = _build_basic_list_query_params(
        {},
        default_sort_by="id",
        default_sort_order="asc",
        default_page_size=10,
    )

    assert params == {
        "q": "",
        "sort_by": "id",
        "sort_order": "asc",
        "page": 0,
        "page_size": 10,
    }


def test_parse_account_ids_param_distinguishes_absent_empty_and_invalid() -> None:
    assert _parse_account_ids_param(None) is None
    assert _parse_account_ids_param("") == []
    assert _parse_account_ids_param("abc,,") == []
    assert _parse_account_ids_param("1,abc,2") == [1, 2]


def test_build_accounts_packs_context_returns_empty_for_invalid_account_ids(
    session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _seed_pack_accounts(session)
    monkeypatch.setattr(
        account_service,
        "select_pack_for_account",
        lambda account, **_: {"account_id": account.id, "pack": f"pack-{account.id}"},
    )

    packs = account_service.build_accounts_packs_context(
        session=session,
        pack_configs_map={},
        account_ids=[],
    )

    assert packs == {}


def test_build_accounts_packs_context_limits_to_requested_account(
    session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _seed_pack_accounts(session)
    monkeypatch.setattr(
        account_service,
        "select_pack_for_account",
        lambda account, **_: {"account_id": account.id, "pack": f"pack-{account.id}"},
    )

    packs = account_service.build_accounts_packs_context(
        session=session,
        pack_configs_map={},
        account_ids=[2],
    )

    assert packs == {2: {"account_id": 2, "pack": "pack-2"}}


def test_build_accounts_packs_context_returns_all_when_account_ids_absent(
    session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _seed_pack_accounts(session)
    monkeypatch.setattr(
        account_service,
        "select_pack_for_account",
        lambda account, **_: {"account_id": account.id, "pack": f"pack-{account.id}"},
    )

    packs = account_service.build_accounts_packs_context(
        session=session,
        pack_configs_map={},
        account_ids=None,
    )

    assert packs == {
        1: {"account_id": 1, "pack": "pack-1"},
        2: {"account_id": 2, "pack": "pack-2"},
    }
