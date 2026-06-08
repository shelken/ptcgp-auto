# -*- coding: utf-8 -*-
"""manage_friendship 收尾行为回归测试。"""

from datetime import datetime

from ptcgp_auto_v2.core.task_state import TaskState
from ptcgp_auto_v2.db.repositories.friend_request_repository import FriendRequestSnapshot
from ptcgp_auto_v2.tasks import manage_friendship
from ptcgp_auto_v2.tasks.manage_friendship import ManageFriendshipTask


def _build_task():
    task = ManageFriendshipTask.__new__(ManageFriendshipTask)
    task.state = TaskState()
    task.requests_to_process = []
    task.current_request = object()
    task._active_request_id = 1
    task._submitted_request_id = 1
    task._returning_to_friend_list = False
    task.reset_action_cache = lambda: None
    task._reset_wait_rounds = lambda: None
    task._log_pending_request_order = lambda stage: None
    task._get_pending_requests = lambda: []
    return task


def test_refresh_without_requests_waits_until_friend_list_before_complete():
    task = _build_task()

    task._refresh_requests()

    assert task._returning_to_friend_list is True
    assert task.is_completed() is False

    result = task._handle_friend_list({})

    assert result.success is True
    assert task.is_completed() is True


def test_defer_last_request_waits_until_friend_list_before_complete():
    task = _build_task()
    request = type("Request", (), {"id": 1})()
    task.requests_to_process = [request]

    task._defer_current_request(request, "test")

    assert task._returning_to_friend_list is True
    assert task.is_completed() is False


def test_get_pending_requests_uses_repository_pending_snapshot(monkeypatch):
    """任务层只请求仓储提供的 pending 快照，并保留统一排序。"""
    calls = []
    rows = [
        FriendRequestSnapshot(
            id=2,
            from_account_id=1,
            to_account_id=3,
            to_friend_id="3",
            to_nickname=None,
            request_type="delete",
            status="deleting",
            failed_reason=None,
            created_at=datetime(2026, 1, 1, 12, 1, 0),
            updated_at=datetime(2026, 1, 1, 12, 1, 0),
        ),
        FriendRequestSnapshot(
            id=1,
            from_account_id=1,
            to_account_id=2,
            to_friend_id="2",
            to_nickname=None,
            request_type="add",
            status="sending",
            failed_reason=None,
            created_at=datetime(2026, 1, 1, 12, 0, 0),
            updated_at=datetime(2026, 1, 1, 12, 0, 0),
        ),
    ]

    class FakeRepository:
        def __init__(self, session):
            calls.append(("init", session))

        def list_manage_friendship_pending_data(self, account_id):
            calls.append(("pending", account_id))
            return rows

    class FakeSessionScope:
        def __enter__(self):
            return "session-1"

        # 变更原因：假上下文管理器只需匹配协议，避免未使用参数触发 vulture。
        def __exit__(self, *_args):
            return False

    monkeypatch.setattr(manage_friendship, "session_scope", lambda: FakeSessionScope())
    monkeypatch.setattr(manage_friendship, "FriendRequestRepository", FakeRepository)

    task = ManageFriendshipTask.__new__(ManageFriendshipTask)
    task._account = type("Account", (), {"id": 1})()

    pending = task._get_pending_requests()

    assert [row.id for row in pending] == [1, 2]
    assert calls == [("init", "session-1"), ("pending", 1)]
