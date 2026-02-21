# -*- coding: utf-8 -*-
"""通知配置常量与默认值测试。"""

from ptcgp_auto_v2.config.constants import (
    HIGH_RARITY_TARGETS,
    NOTIFICATION_TASK_STATUS_DEFAULTS,
)


def test_scene_options_keep_expected_order():
    """通知场景常量应保持稳定顺序。"""
    from ptcgp_auto_v2.config.notification import NOTIFICATION_SCENE_OPTIONS

    assert NOTIFICATION_SCENE_OPTIONS == [
        "rare_card_obtained",
        "task_status",
        "system_warning",
    ]


def test_build_default_scene_config_uses_project_defaults():
    """默认场景配置应复用项目级默认常量。"""
    from ptcgp_auto_v2.config.notification import build_default_scene_config

    rare_card_defaults = build_default_scene_config("rare_card_obtained")
    task_status_defaults = build_default_scene_config("task_status")

    assert rare_card_defaults["extra_config"]["notify_by_rarity"] == list(
        HIGH_RARITY_TARGETS
    )
    assert task_status_defaults["extra_config"]["notify_on"] == list(
        NOTIFICATION_TASK_STATUS_DEFAULTS
    )


def test_build_default_scene_config_returns_deep_copy():
    """多次构建默认配置时，返回值不应共享可变对象。"""
    from ptcgp_auto_v2.config.notification import build_default_scene_config

    first = build_default_scene_config("task_status")
    second = build_default_scene_config("task_status")

    first["extra_config"]["notify_task_types"].append("open_pack")

    assert second["extra_config"]["notify_task_types"] == []
