# -*- coding: utf-8 -*-
"""manage_friendship 收尾行为回归测试。"""

from ptcgp_auto_v2.core.task_state import TaskState
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
