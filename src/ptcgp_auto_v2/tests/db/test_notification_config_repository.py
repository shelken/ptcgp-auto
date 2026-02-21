# -*- coding: utf-8 -*-
"""
NotificationConfigRepository 单元测试
"""

import pytest
from unittest.mock import patch
from sqlmodel import SQLModel, create_engine

from ptcgp_auto_v2.db.models import NotificationConfig


@pytest.fixture(name="engine")
def engine_fixture():
    engine = create_engine("sqlite:///:memory:")
    SQLModel.metadata.create_all(engine)
    return engine


@pytest.fixture(name="mock_get_engine")
def mock_get_engine_fixture(engine):
    with patch(
        "ptcgp_auto_v2.db.repositories.notification_config_repository.get_engine",
        return_value=engine,
    ):
        yield


class TestNotificationConfigRepositoryGetOrCreate:
    """获取或创建配置测试"""

    def test_create_default_config_for_rare_card(self, mock_get_engine):
        from ptcgp_auto_v2.db.repositories.notification_config_repository import (
            NotificationConfigRepository,
        )

        repo = NotificationConfigRepository()
        config = repo.get_or_create("rare_card_obtained")

        assert config.id is not None
        assert config.scene == "rare_card_obtained"
        assert config.enabled is True
        assert config.enabled_webhook is False

    def test_create_default_config_for_task_status(self, mock_get_engine):
        from ptcgp_auto_v2.db.repositories.notification_config_repository import (
            NotificationConfigRepository,
        )

        repo = NotificationConfigRepository()
        config = repo.get_or_create("task_status")

        assert config.scene == "task_status"
        assert config.enabled is True

    def test_create_default_config_for_system_warning(self, mock_get_engine):
        from ptcgp_auto_v2.db.repositories.notification_config_repository import (
            NotificationConfigRepository,
        )

        repo = NotificationConfigRepository()
        config = repo.get_or_create("system_warning")

        assert config.scene == "system_warning"
        assert config.enabled is True

    def test_returns_existing_config(self, mock_get_engine):
        from ptcgp_auto_v2.db.repositories.notification_config_repository import (
            NotificationConfigRepository,
        )

        repo = NotificationConfigRepository()
        config1 = repo.get_or_create("task_status")
        config2 = repo.get_or_create("task_status")

        assert config1.id == config2.id


class TestNotificationConfigRepositoryUpdate:
    """更新配置测试"""

    def test_update_enabled(self, mock_get_engine):
        from ptcgp_auto_v2.db.repositories.notification_config_repository import (
            NotificationConfigRepository,
        )

        repo = NotificationConfigRepository()
        repo.get_or_create("task_status")

        updated = repo.update(scene="task_status", enabled=False)

        assert updated.enabled is False

    def test_update_enabled_webhook(self, mock_get_engine):
        from ptcgp_auto_v2.db.repositories.notification_config_repository import (
            NotificationConfigRepository,
        )

        repo = NotificationConfigRepository()
        repo.get_or_create("task_status")

        updated = repo.update(scene="task_status", enabled_webhook=True)

        assert updated.enabled_webhook is True

    def test_update_extra_config(self, mock_get_engine):
        from ptcgp_auto_v2.db.repositories.notification_config_repository import (
            NotificationConfigRepository,
        )

        repo = NotificationConfigRepository()
        repo.get_or_create("rare_card_obtained")

        new_extra = {
            "notify_by_rarity": ["RR", "UR"],
            "notify_card_ids": [123, 456],
        }
        updated = repo.update(scene="rare_card_obtained", extra_config=new_extra)

        import json

        saved_extra = json.loads(updated.extra_config)
        assert saved_extra["notify_by_rarity"] == ["RR", "UR"]


class TestNotificationConfigRepositoryExtraConfig:
    """扩展配置测试"""

    def test_get_extra_config_for_rare_card(self, mock_get_engine):
        from ptcgp_auto_v2.db.repositories.notification_config_repository import (
            NotificationConfigRepository,
        )

        repo = NotificationConfigRepository()
        extra = repo.get_extra_config("rare_card_obtained")

        assert "notify_by_rarity" in extra
        assert "notify_card_ids" in extra

    def test_get_extra_config_for_task_status(self, mock_get_engine):
        from ptcgp_auto_v2.db.repositories.notification_config_repository import (
            NotificationConfigRepository,
        )

        repo = NotificationConfigRepository()
        extra = repo.get_extra_config("task_status")

        assert "notify_task_types" in extra
        assert "notify_on" in extra


class TestNotificationConfigRepositoryEnabled:
    """启用状态测试"""

    def test_is_enabled_default_true(self, mock_get_engine):
        from ptcgp_auto_v2.db.repositories.notification_config_repository import (
            NotificationConfigRepository,
        )

        repo = NotificationConfigRepository()
        assert repo.is_enabled("task_status") is True

    def test_is_enabled_after_disable(self, mock_get_engine):
        from ptcgp_auto_v2.db.repositories.notification_config_repository import (
            NotificationConfigRepository,
        )

        repo = NotificationConfigRepository()
        # 先确保配置存在
        repo.get_or_create("task_status")
        repo.update(scene="task_status", enabled=False)

        assert repo.is_enabled("task_status") is False

    def test_is_webhook_enabled_default_false(self, mock_get_engine):
        from ptcgp_auto_v2.db.repositories.notification_config_repository import (
            NotificationConfigRepository,
        )

        repo = NotificationConfigRepository()
        assert repo.is_webhook_enabled("task_status") is False

    def test_is_webhook_enabled_requires_both_enabled(self, mock_get_engine):
        from ptcgp_auto_v2.db.repositories.notification_config_repository import (
            NotificationConfigRepository,
        )

        repo = NotificationConfigRepository()

        # 仅开启 webhook
        repo.update(scene="task_status", enabled=False, enabled_webhook=True)
        assert repo.is_webhook_enabled("task_status") is False

        # 同时开启
        repo.update(scene="task_status", enabled=True, enabled_webhook=True)
        assert repo.is_webhook_enabled("task_status") is True


class TestNotificationConfigRepositoryEnsureAllScenes:
    """确保所有场景配置测试"""

    def test_ensure_all_scenes_creates_missing(self, mock_get_engine):
        from ptcgp_auto_v2.db.repositories.notification_config_repository import (
            NotificationConfigRepository,
        )

        repo = NotificationConfigRepository()
        repo.ensure_all_scenes()

        configs = repo.get_all()
        scenes = [c.scene for c in configs]

        assert "rare_card_obtained" in scenes
        assert "task_status" in scenes
        assert "system_warning" in scenes
