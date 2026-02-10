# -*- coding: utf-8 -*-

import pytest
from sqlmodel import SQLModel, Session, create_engine, select

from ptcgp_auto_v2.db import engine as db_engine
from ptcgp_auto_v2.db.models import Account, AccountFriendRequest, AccountFriendship
from ptcgp_auto_v2.db.repositories import FriendRequestRepository
from ptcgp_auto_v2.services.friendship_service import FriendshipService


@pytest.fixture
def isolated_engine(monkeypatch):
    """为服务层测试提供隔离数据库引擎。"""
    test_engine = create_engine("sqlite:///:memory:")
    SQLModel.metadata.create_all(test_engine)
    monkeypatch.setattr(db_engine, "_engine", test_engine)
    yield test_engine
    monkeypatch.setattr(db_engine, "_engine", None)


def test_create_delete_request_requires_existing_friendship(isolated_engine):
    """非好友关系不应创建删除请求。"""
    with Session(isolated_engine) as session:
        account = Account(game_id="acc_delete_guard")
        session.add(account)
        session.commit()
        session.refresh(account)
        account_id = account.id

    request = FriendshipService.create_delete_request(
        account_id=account_id,
        friend_id="9999000011112222",
    )

    assert request is None

    with Session(isolated_engine) as session:
        rows = session.exec(select(AccountFriendRequest)).all()
        assert rows == []


def test_create_delete_request_keeps_target_friend_id(isolated_engine):
    """删除指定好友时，应写入 to_friend_id 且移除关系记录。"""
    with Session(isolated_engine) as session:
        account = Account(game_id="acc_delete_target")
        session.add(account)
        session.commit()
        session.refresh(account)
        account_id = account.id

        friendship = AccountFriendship(
            account_id=account_id,
            friend_id="1234567890123456",
            friend_account_id=None,
        )
        session.add(friendship)
        session.commit()

    request = FriendshipService.create_delete_request(
        account_id=account_id,
        friend_id="1234567890123456",
    )

    assert request is not None
    assert request.request_type == "delete"
    assert request.status == "deleting"
    assert request.to_friend_id == "1234567890123456"

    with Session(isolated_engine) as session:
        friendship_rows = session.exec(
            select(AccountFriendship).where(
                AccountFriendship.account_id == account_id,
                AccountFriendship.friend_id == "1234567890123456",
            )
        ).all()
        assert friendship_rows == []


def test_delete_pending_request_record_allows_pending_only(isolated_engine):
    """管理页仅允许删除未执行的申请记录。"""
    with Session(isolated_engine) as session:
        account = Account(game_id="acc_pending_delete")
        session.add(account)
        session.commit()
        session.refresh(account)
        account_id = account.id

        pending_row = AccountFriendRequest(
            from_account_id=account_id,
            to_friend_id="1111222233334444",
            request_type="add",
            status="sending",
        )
        deleting_row = AccountFriendRequest(
            from_account_id=account_id,
            to_friend_id="1111222233334446",
            request_type="delete",
            status="deleting",
        )
        done_row = AccountFriendRequest(
            from_account_id=account_id,
            to_friend_id="1111222233335555",
            request_type="add",
            status="completed",
        )
        session.add(pending_row)
        session.add(deleting_row)
        session.add(done_row)
        session.commit()
        session.refresh(pending_row)
        session.refresh(deleting_row)
        session.refresh(done_row)

    repo = FriendRequestRepository()
    assert repo.delete_pending(request_id=pending_row.id) is True
    assert repo.delete_pending(request_id=deleting_row.id) is True
    assert repo.delete_pending(request_id=done_row.id) is False

    with Session(isolated_engine) as session:
        rows = session.exec(select(AccountFriendRequest)).all()
        assert len(rows) == 1
        assert rows[0].id == done_row.id
