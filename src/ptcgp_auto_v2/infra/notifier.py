# -*- coding: utf-8 -*-
"""
通知器模块

提供统一的通知入口，支持站内通知和企业微信 Webhook 推送。
"""

import logging
import os
from datetime import datetime
from typing import TYPE_CHECKING, Optional

import requests

from ptcgp_auto_v2.config.assets import CARD_IMAGE_CDN_BASE_URL
from ptcgp_auto_v2.config.constants import NOTIFICATION_TASK_STATUS_DEFAULTS
from ptcgp_auto_v2.config.notification import (
    SCENE_RARE_CARD,
    SCENE_SYSTEM_WARNING,
    SCENE_TASK_STATUS,
)
from ptcgp_auto_v2.config.settings import (
    build_wecom_webhook_url_from_key,
    load_dotenv,
)
from ptcgp_auto_v2.config.rarity_icons import get_rarity_display
from ptcgp_auto_v2.db.repositories import (
    NotificationConfigRepository,
    NotificationRepository,
)

if TYPE_CHECKING:
    from ptcgp_auto_v2.db.models import Account, Card, TaskInstance

logger = logging.getLogger(__name__)


TASK_STATUS_TEXT_MAP = {
    "failed": "失败",
    "blocked": "阻塞",
    "timeout": "超时",
    "success": "成功",
}


class Notifier:
    """统一通知入口"""

    def __init__(self, webhook_url: Optional[str] = None):
        self.webhook_url = self._resolve_webhook_url(webhook_url)
        self._config_repo = NotificationConfigRepository()
        self._notification_repo = NotificationRepository()

    @staticmethod
    def _resolve_webhook_url(
        explicit_webhook_url: Optional[str] = None,
    ) -> Optional[str]:
        """解析企业微信 Webhook URL（优先级：显式参数 > 环境变量 > .env > 默认空）。"""
        load_dotenv()

        if explicit_webhook_url:
            return explicit_webhook_url

        webhook_url = os.environ.get("PTCGP_WEBHOOK_URL")
        if webhook_url:
            return webhook_url

        webhook_key = os.environ.get("PTCGP_NOTIFY_KEY") or os.environ.get("NOTIFY_KEY")
        if webhook_key:
            return build_wecom_webhook_url_from_key(webhook_key)

        return None

    def notify(
        self,
        scene: str,
        title: str,
        content: str,
        account_id: Optional[int] = None,
        task_instance_id: Optional[int] = None,
        image_url: Optional[str] = None,
    ) -> bool:
        """
        发送通知（站内 + 企微 Webhook）

        Args:
            scene: 场景名称
            title: 通知标题
            content: Markdown 内容
            account_id: 关联账号 ID
            task_instance_id: 关联任务实例 ID
            image_url: 图片 URL（用于企微推送）

        Returns:
            是否成功发送站内通知
        """
        config = self._config_repo.get_or_create(scene)

        if not config.enabled:
            logger.debug(f"通知场景 {scene} 未启用，跳过")
            return False

        self._notification_repo.create(
            scene=scene,
            title=title,
            content=content,
            account_id=account_id,
            task_instance_id=task_instance_id,
        )
        logger.info(f"站内通知已创建: [{scene}] {title}")

        if config.enabled_webhook and self.webhook_url:
            self._send_webhook(title, content, image_url)

        return True

    @staticmethod
    def _format_now() -> str:
        """返回统一格式的本地时间字符串。"""
        return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    @staticmethod
    def _resolve_account_name(account: Optional["Account"]) -> str:
        """解析账号显示名称，兼容空账号场景。"""
        if account is None:
            return "未知账号"

        primary_name = account.nickname or account.display_name or str(account.id)
        account_id = getattr(account, "id", None)
        account_id_text = str(account_id) if account_id is not None else ""
        if account_id_text and primary_name != account_id_text:
            return f"{primary_name} ({account_id_text})"
        return primary_name

    @staticmethod
    def _is_rare_card_notifiable(
        rarity: str,
        card_id: Optional[int],
        notify_by_rarity: list[str],
        notify_card_ids: list[int],
    ) -> bool:
        """判断稀有卡牌是否满足通知条件。"""
        return card_id in notify_card_ids or rarity in notify_by_rarity

    @staticmethod
    def _is_task_status_notifiable(
        task_type: str,
        status: str,
        notify_task_types: list[str],
        notify_on: list[str],
    ) -> bool:
        """判断任务状态是否满足通知条件。"""
        if notify_task_types and task_type not in notify_task_types:
            logger.debug(f"任务类型 {task_type} 不在通知列表中")
            return False
        if status not in notify_on:
            logger.debug(f"状态 {status} 不在通知条件中")
            return False
        return True

    def _load_scene_extra_config(
        self,
        scene: str,
    ) -> tuple[bool, dict]:
        """加载场景配置，返回 (是否启用, 扩展配置)。"""
        config = self._config_repo.get_or_create(scene)
        if not config.enabled:
            return False, {}
        return True, self._config_repo.get_extra_config(scene)

    @staticmethod
    def _build_rare_card_content(
        account_name: str,
        card_name: str,
        rarity_display: str,
        event_message: str,
        image_url: Optional[str] = None,
    ) -> str:
        """构建稀有卡牌通知正文。"""
        content = (
            f"账号: {account_name}\n"
            f"事件: {event_message}\n"
            f"卡牌: {card_name}\n"
            f"稀有度: {rarity_display}"
        )
        if image_url:
            content += f"\n\n![{card_name}]({image_url})"
        return content

    @staticmethod
    def _build_task_status_content(
        account_name: str,
        task_type: str,
        status_text: str,
        message: str,
        time_text: str,
    ) -> str:
        """构建任务状态通知正文。"""
        return (
            f"账号: {account_name}\n"
            f"任务: {task_type}\n"
            f"状态: {status_text}\n"
            f"原因: {message}\n"
            f"时间: {time_text}"
        )

    @staticmethod
    def _build_system_warning_content(message: str, time_text: str) -> str:
        """构建系统警告通知正文。"""
        return f"{message}\n时间: {time_text}"

    @staticmethod
    def _build_webhook_payload(
        title: str,
        content: str,
        image_url: Optional[str] = None,
    ) -> dict:
        """构建企业微信 webhook payload。"""
        markdown_content = f"## {title}\n\n{content}"
        if image_url:
            markdown_content += f"\n\n![card]({image_url})"
            return {
                "msgtype": "markdown_v2",
                "markdown_v2": {"content": markdown_content},
            }
        return {"msgtype": "markdown", "markdown": {"content": markdown_content}}

    def notify_rare_card(
        self,
        account: "Account",
        card: "Card",
        rarity: str,
        image_url: Optional[str] = None,
        message: Optional[str] = None,
    ) -> bool:
        """
        稀有卡牌通知

        Args:
            account: 账号
            card: 卡牌
            rarity: 稀有度代码（如 R, RR, SR）
            image_url: 卡牌图片 URL

        Returns:
            是否发送通知
        """
        enabled, extra_config = self._load_scene_extra_config(SCENE_RARE_CARD)
        if not enabled:
            return False
        notify_by_rarity = extra_config.get("notify_by_rarity", [])
        notify_card_ids = extra_config.get("notify_card_ids", [])

        card_id = card.id

        if not self._is_rare_card_notifiable(
            rarity=rarity,
            card_id=card_id,
            notify_by_rarity=notify_by_rarity,
            notify_card_ids=notify_card_ids,
        ):
            logger.debug(f"卡牌 {card.name} ({rarity}) 不符合通知条件")
            return False

        account_name = self._resolve_account_name(account)
        rarity_display = get_rarity_display(rarity, "zh_CN")

        title = "稀有卡牌通知"
        resolved_image_url = self._resolve_card_image_url(card, image_url)
        content = self._build_rare_card_content(
            account_name=account_name,
            card_name=card.name,
            rarity_display=rarity_display,
            event_message=message or "开出稀有卡牌",
            image_url=resolved_image_url,
        )

        return self.notify(
            scene=SCENE_RARE_CARD,
            title=title,
            content=content,
            account_id=account.id,
            image_url=resolved_image_url,
        )

    @staticmethod
    def _resolve_card_image_url(
        card: "Card", image_url: Optional[str]
    ) -> Optional[str]:
        """解析卡牌图片 URL：优先绝对 URL，否则按 set_code/number 生成。"""
        if image_url and image_url.startswith(("http://", "https://")):
            return image_url

        set_code = getattr(card, "set_code", None)
        card_number = getattr(card, "number", None)
        if set_code and card_number is not None:
            return f"{CARD_IMAGE_CDN_BASE_URL}/{set_code}/{card_number}.png"

        return None

    def notify_task_status(
        self,
        task_instance: "TaskInstance",
        status: str,
        message: str,
    ) -> bool:
        """
        任务状态通知

        Args:
            task_instance: 任务实例
            status: 状态（failed/blocked/timeout/success）
            message: 状态消息

        Returns:
            是否发送通知
        """
        enabled, extra_config = self._load_scene_extra_config(SCENE_TASK_STATUS)
        if not enabled:
            return False
        notify_task_types = extra_config.get("notify_task_types", [])
        notify_on = extra_config.get(
            "notify_on", list(NOTIFICATION_TASK_STATUS_DEFAULTS)
        )

        task_type = task_instance.task_type

        if not self._is_task_status_notifiable(
            task_type=task_type,
            status=status,
            notify_task_types=notify_task_types,
            notify_on=notify_on,
        ):
            return False

        account = task_instance.account
        account_name = self._resolve_account_name(account)

        status_text = TASK_STATUS_TEXT_MAP.get(status, status)
        now_text = self._format_now()

        title = "任务状态通知"
        content = self._build_task_status_content(
            account_name=account_name,
            task_type=task_type,
            status_text=status_text,
            message=message,
            time_text=now_text,
        )

        return self.notify(
            scene=SCENE_TASK_STATUS,
            title=title,
            content=content,
            account_id=account.id if account else None,
            task_instance_id=task_instance.id,
        )

    def notify_system_warning(
        self,
        title: str,
        message: str,
    ) -> bool:
        """
        系统警告通知

        Args:
            title: 警告标题
            message: 警告内容

        Returns:
            是否发送通知
        """
        content = self._build_system_warning_content(message, self._format_now())

        return self.notify(
            scene=SCENE_SYSTEM_WARNING,
            title=title,
            content=content,
        )

    def send_webhook_test(self) -> bool:
        """发送企业微信测试消息（仅 Webhook，不落库）。"""
        title = "企业微信通知测试"
        content = f"这是一条来自 PTCGP Auto Web 的测试消息\n时间: {self._format_now()}"
        return self.send_webhook_notification(title=title, content=content)

    def send_webhook_notification(
        self,
        title: str,
        content: str,
        image_url: Optional[str] = None,
    ) -> bool:
        """直接发送指定通知内容到企业微信（不落库）。"""
        return self._send_webhook(title=title, content=content, image_url=image_url)

    def _send_webhook(
        self,
        title: str,
        content: str,
        image_url: Optional[str] = None,
    ) -> bool:
        """
        发送企微 Webhook

        Args:
            title: 标题
            content: Markdown 内容
            image_url: 图片 URL

        Returns:
            是否发送成功
        """
        if not self.webhook_url:
            logger.warning("Webhook URL 未配置，跳过推送")
            return False

        payload = self._build_webhook_payload(title, content, image_url)

        try:
            response = requests.post(
                self.webhook_url,
                json=payload,
                timeout=5,
            )
            if response.status_code == 200:
                logger.info(f"企微 Webhook 推送成功: {title}")
                return True
            else:
                logger.warning(
                    f"企微 Webhook 推送失败: {response.status_code} - {response.text}"
                )
                return False
        except Exception as e:
            logger.warning(f"企微 Webhook 推送异常: {e}")
            return False


_notifier_instance: Optional[Notifier] = None


def get_notifier() -> Notifier:
    """获取全局 Notifier 实例"""
    global _notifier_instance
    if _notifier_instance is None:
        _notifier_instance = Notifier()
    return _notifier_instance
