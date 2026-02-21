# -*- coding: utf-8 -*-
"""
NotificationRepository 单元测试
"""

import pytest
from unittest.mock import patch
from sqlmodel import Session, SQLModel, create_engine

from ptcgp_auto_v2.db.models import Notification
from ptcgp_auto_v2.db.repositories.notification_repository import NotificationRepository


@pytest.fixture(name="engine")
def engine_fixture():
    engine = create_engine("sqlite:///:memory:")
    SQLModel.metadata.create_all(engine)
    return engine


@pytest.fixture(name="mock_get_engine")
def mock_get_engine_fixture(engine):
    with patch(
        "ptcgp_auto_v2.db.repositories.notification_repository.get_engine",
        return_value=engine,
    ):
        yield


class TestNotificationRepositoryCreate:
    """创建通知测试"""

    def test_create_notification_with_required_fields(self, mock_get_engine):
        """测试创建通知 - 仅必填字段"""
        repo = NotificationRepository()

        notification = repo.create(
            scene="task_status",
            title="任务失败",
            content="账号 test 开包任务失败",
        )

        assert notification.id is not None
        assert notification.scene == "task_status"
        assert notification.title == "任务失败"
        assert notification.content == "账号 test 开包任务失败"
        assert notification.is_read is False
        assert notification.related_account_id is None
        assert notification.related_task_instance_id is None

    def test_create_notification_with_all_fields(self, mock_get_engine):
        """测试创建通知 - 全部字段"""
        repo = NotificationRepository()

        notification = repo.create(
            scene="rare_card_obtained",
            title="稀有卡牌",
            content="开出 ★★★★ 皮卡丘",
            account_id=1,
            task_instance_id=100,
        )

        assert notification.related_account_id == 1
        assert notification.related_task_instance_id == 100


class TestNotificationRepositoryList:
    """列表查询测试"""

    def test_list_all_notifications(self, mock_get_engine, engine):
        repo = NotificationRepository()
        repo.create(scene="task_status", title="通知1", content="内容1")
        repo.create(scene="rare_card_obtained", title="通知2", content="内容2")
        repo.create(scene="system_warning", title="通知3", content="内容3")

        all_notifications = repo.list()
        assert len(all_notifications) == 3

    def test_list_filter_by_scene(self, mock_get_engine):
        repo = NotificationRepository()
        repo.create(scene="task_status", title="通知1", content="内容1")
        repo.create(scene="rare_card_obtained", title="通知2", content="内容2")

        task_notifications = repo.list(scene="task_status")
        assert len(task_notifications) == 1
        assert task_notifications[0].scene == "task_status"

    def test_list_filter_by_account(self, mock_get_engine):
        repo = NotificationRepository()
        repo.create(scene="task_status", title="通知1", content="内容1", account_id=1)
        repo.create(scene="task_status", title="通知2", content="内容2", account_id=2)

        account_notifications = repo.list(account_id=1)
        assert len(account_notifications) == 1

    def test_list_pagination(self, mock_get_engine):
        repo = NotificationRepository()
        for i in range(25):
            repo.create(scene="task_status", title=f"通知{i}", content=f"内容{i}")

        page1 = repo.list(page=0, page_size=10)
        page2 = repo.list(page=1, page_size=10)

        assert len(page1) == 10
        assert len(page2) == 10


class TestNotificationRepositoryCount:
    """计数测试"""

    def test_count_all(self, mock_get_engine):
        repo = NotificationRepository()
        repo.create(scene="task_status", title="通知1", content="内容1")
        repo.create(scene="rare_card_obtained", title="通知2", content="内容2")

        assert repo.count() == 2

    def test_count_unread(self, mock_get_engine):
        repo = NotificationRepository()
        repo.create(scene="task_status", title="通知1", content="内容1")
        repo.create(scene="task_status", title="通知2", content="内容2")

        assert repo.count_unread() == 2

    def test_count_filter_by_scene(self, mock_get_engine):
        repo = NotificationRepository()
        repo.create(scene="task_status", title="通知1", content="内容1")
        repo.create(scene="rare_card_obtained", title="通知2", content="内容2")

        assert repo.count(scene="task_status") == 1


class TestNotificationRepositoryMarkRead:
    """标记已读测试"""

    def test_mark_single_as_read(self, mock_get_engine):
        repo = NotificationRepository()
        notification = repo.create(scene="task_status", title="通知", content="内容")

        assert notification.is_read is False

        repo.mark_as_read(notification.id)

        updated = repo.get_by_id(notification.id)
        assert updated.is_read is True

    def test_mark_all_as_read(self, mock_get_engine):
        repo = NotificationRepository()
        repo.create(scene="task_status", title="通知1", content="内容1")
        repo.create(scene="task_status", title="通知2", content="内容2")
        repo.create(scene="rare_card_obtained", title="通知3", content="内容3")

        count = repo.mark_all_as_read(scene="task_status")
        assert count == 2
        assert repo.count_unread() == 1

    def test_mark_all_as_read_by_account(self, mock_get_engine):
        repo = NotificationRepository()
        repo.create(scene="task_status", title="通知1", content="内容1", account_id=1)
        repo.create(scene="task_status", title="通知2", content="内容2", account_id=1)
        repo.create(scene="task_status", title="通知3", content="内容3", account_id=2)

        count = repo.mark_all_as_read(account_id=1)
        assert count == 2


class TestNotificationRepositoryDelete:
    """删除测试"""

    def test_delete_notification(self, mock_get_engine):
        repo = NotificationRepository()
        notification = repo.create(scene="task_status", title="通知", content="内容")

        assert repo.delete(notification.id) is True
        assert repo.get_by_id(notification.id) is None

    def test_delete_nonexistent(self, mock_get_engine):
        repo = NotificationRepository()
        assert repo.delete(999) is False
