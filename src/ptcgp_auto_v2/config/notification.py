# -*- coding: utf-8 -*-
"""通知模块共享常量与默认配置。"""

from copy import deepcopy
from typing import Any

from ptcgp_auto_v2.config.constants import (
    HIGH_RARITY_TARGETS,
    NOTIFICATION_TASK_STATUS_DEFAULTS,
    NOTIFICATION_TASK_STATUS_OPTIONS as TASK_STATUS_OPTIONS_DEFAULT,
)


SCENE_RARE_CARD = "rare_card_obtained"
SCENE_TASK_STATUS = "task_status"
SCENE_SYSTEM_WARNING = "system_warning"

NOTIFICATION_SCENE_OPTIONS = [
    SCENE_RARE_CARD,
    SCENE_TASK_STATUS,
    SCENE_SYSTEM_WARNING,
]

NOTIFICATION_SCENE_LABEL_KEYS = {
    SCENE_RARE_CARD: "notification_scene_rare_card",
    SCENE_TASK_STATUS: "notification_scene_task_status",
    SCENE_SYSTEM_WARNING: "notification_scene_system_warning",
}

NOTIFICATION_TASK_STATUS_OPTIONS = list(TASK_STATUS_OPTIONS_DEFAULT)

_SCENE_DEFAULTS: dict[str, dict[str, Any]] = {
    SCENE_RARE_CARD: {
        "enabled": True,
        "enabled_webhook": False,
        "extra_config": {
            "notify_by_rarity": list(HIGH_RARITY_TARGETS),
            "notify_card_ids": [],
        },
    },
    SCENE_TASK_STATUS: {
        "enabled": True,
        "enabled_webhook": False,
        "extra_config": {
            "notify_task_types": [],
            "notify_on": list(NOTIFICATION_TASK_STATUS_DEFAULTS),
        },
    },
    SCENE_SYSTEM_WARNING: {
        "enabled": True,
        "enabled_webhook": False,
        "extra_config": {},
    },
}


def build_default_scene_config(scene: str) -> dict[str, Any]:
    """按场景构建默认通知配置（返回深拷贝）。"""
    fallback = {"enabled": True, "enabled_webhook": False, "extra_config": {}}
    return deepcopy(_SCENE_DEFAULTS.get(scene, fallback))
