# -*- coding: utf-8 -*-
"""
通知配置 Repository

提供通知配置的数据访问方法。
"""

import json
from datetime import datetime
from typing import Any, Dict, Optional

from sqlmodel import select

from ptcgp_auto_v2.config.notification import (
    NOTIFICATION_SCENE_OPTIONS,
    build_default_scene_config,
)
from ptcgp_auto_v2.db.models import NotificationConfig
from .base import BaseRepository


class NotificationConfigRepository(BaseRepository):
    """通知配置数据访问层"""

    SCENES = list(NOTIFICATION_SCENE_OPTIONS)

    def get_by_scene(self, scene: str) -> Optional[NotificationConfig]:
        """根据场景获取配置"""
        statement = select(NotificationConfig).where(NotificationConfig.scene == scene)
        return self.session.exec(statement).first()

    def get_or_create(self, scene: str) -> NotificationConfig:
        """获取或创建配置"""
        config = self.get_by_scene(scene)
        if config:
            return config

        default_config = self._get_default_config(scene)
        config = NotificationConfig(
            scene=scene,
            enabled=default_config.get("enabled", True),
            enabled_webhook=default_config.get("enabled_webhook", False),
            extra_config=json.dumps(default_config.get("extra_config", {})),
        )
        self.session.add(config)
        self._finish_write(config)
        return config

    def get_all(self) -> list[NotificationConfig]:
        """获取所有配置"""
        statement = select(NotificationConfig)
        return list(self.session.exec(statement).all())

    def ensure_all_scenes(self) -> None:
        """确保所有场景都有配置"""
        for scene in self.SCENES:
            self.get_or_create(scene)

    def update(
        self,
        scene: str,
        enabled: Optional[bool] = None,
        enabled_webhook: Optional[bool] = None,
        extra_config: Optional[Dict[str, Any]] = None,
    ) -> Optional[NotificationConfig]:
        """更新配置"""
        config = self.session.exec(
            select(NotificationConfig).where(NotificationConfig.scene == scene)
        ).first()
        if not config:
            return None

        if enabled is not None:
            config.enabled = enabled
        if enabled_webhook is not None:
            config.enabled_webhook = enabled_webhook
        if extra_config is not None:
            config.extra_config = json.dumps(extra_config)
        config.updated_at = datetime.now()
        self.session.add(config)
        self._finish_write(config)
        return config

    def get_extra_config(self, scene: str) -> Dict[str, Any]:
        """获取场景的扩展配置"""
        config = self.get_or_create(scene)
        try:
            return json.loads(config.extra_config or "{}")
        except json.JSONDecodeError:
            return {}

    def is_enabled(self, scene: str) -> bool:
        """检查场景是否启用"""
        config = self.get_or_create(scene)
        return config.enabled

    def is_webhook_enabled(self, scene: str) -> bool:
        """检查场景是否启用 Webhook"""
        config = self.get_or_create(scene)
        return config.enabled and config.enabled_webhook

    def _get_default_config(self, scene: str) -> Dict[str, Any]:
        """获取场景默认配置"""
        return build_default_scene_config(scene)
