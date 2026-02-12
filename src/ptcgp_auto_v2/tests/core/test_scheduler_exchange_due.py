# -*- coding: utf-8 -*-
from datetime import datetime, timedelta

from ptcgp_auto_v2.core.scheduler import Scheduler


class FakeExchangeRequest:
    """用于测试的交换请求对象。"""

    def __init__(self, from_account_id: int, next_check_at: datetime | None):
        self.from_account_id = from_account_id
        self.next_check_at = next_check_at


class FakeExchangeRequestRepo:
    """用于测试的交换请求仓储。"""

    def __init__(self, requests):
        self._requests = requests

    def list_sended_requests(self):
        return self._requests


class FakeTaskRepo:
    """用于测试的任务仓储。"""

    def __init__(self):
        self.calls: list[tuple[int, str, str]] = []

    def ensure_pending(self, account_id: int, task_type: str, reset_type: str):
        self.calls.append((account_id, task_type, reset_type))


def test_scheduler_only_wakes_due_exchange_requests():
    """仅唤醒 next_check_at <= now 的请求对应账号。"""
    scheduler = Scheduler(device_addresses=[])
    task_repo = FakeTaskRepo()
    now = datetime.now()

    scheduler._task_instance_repo = task_repo
    scheduler._exchange_card_request_repo = FakeExchangeRequestRepo(
        requests=[
            FakeExchangeRequest(
                from_account_id=1, next_check_at=now - timedelta(seconds=1)
            ),
            FakeExchangeRequest(
                from_account_id=2, next_check_at=now + timedelta(minutes=5)
            ),
            FakeExchangeRequest(from_account_id=3, next_check_at=None),
        ]
    )

    scheduler._wake_due_exchange_cards_tasks(now=now)

    assert task_repo.calls == [(1, "exchange_cards", "once")]
