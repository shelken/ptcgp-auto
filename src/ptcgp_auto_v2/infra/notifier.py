# -*- coding: utf-8 -*-
"""
通知器模块

提供统一的通知入口，支持站内通知和企业微信 Webhook 推送。
重构简化版：内联单行/单次使用的静态方法，保持公共接口不变。
"""

import logging
import os
from datetime import datetime
from typing import TYPE_CHECKING, Protocol, Optional

import requests

from ptcgp_auto_v2.config.assets import build_card_cdn_image_url
from ptcgp_auto_v2.config.constants import NOTIFICATION_TASK_STATUS_DEFAULTS
from ptcgp_auto_v2.config.lang import (
    DEFAULT_LOCALE,
    TASK_LOCALE_TO_WEB_LANG,
    resolve_localized_text,
)
from ptcgp_auto_v2.config.notification import (
    SCENE_RARE_CARD,
    SCENE_TASK_STATUS,
)
from ptcgp_auto_v2.config.rarity_icons import get_rarity_display
from ptcgp_auto_v2.config.settings import (
    build_wecom_webhook_url_from_key,
)
from ptcgp_auto_v2.db.engine import session_scope
from ptcgp_auto_v2.db.repositories import (
    NotificationConfigRepository,
    NotificationRepository,
)

class TaskStatusAccount(Protocol):
    """任务状态通知所需账号字段。"""

    id: int | None
    nickname: str | None
    display_name: str


if TYPE_CHECKING:
    from ptcgp_auto_v2.db.models import Account, TaskInstance

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

    def _resolve_webhook_url(self, explicit_url: Optional[str] = None) -> Optional[str]:
        """解析企业微信 Webhook URL（优先级：显式参数 > 环境变量 > 默认空）。"""
        if explicit_url:
            return explicit_url
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
        card_id: Optional[int] = None,
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
            image_url: 图片 URL（用于构建通知正文）
        Returns:
            是否成功发送站内通知
        """
        enabled_webhook = False
        with session_scope() as session:
            config_repo = NotificationConfigRepository(session)
            notification_repo = NotificationRepository(session)
            config = config_repo.get_or_create(scene)
            if not config.enabled:
                logger.debug(f"通知场景 {scene} 未启用，跳过")
                return False
            enabled_webhook = bool(config.enabled and config.enabled_webhook)

            notification_repo.create(
                scene=scene,
                title=title,
                content=content,
                account_id=account_id,
                card_id=card_id,
                task_instance_id=task_instance_id,
            )
        logger.info(f"站内通知已创建: [{scene}] {title}")

        if enabled_webhook and self.webhook_url:
            self._send_webhook(title, content)

        return True

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

    def _load_scene_extra_config(self, scene: str) -> tuple[bool, dict]:
        """加载场景配置，返回 (是否启用, 扩展配置)。"""
        with session_scope() as session:
            config_repo = NotificationConfigRepository(session)
            config = config_repo.get_or_create(scene)
            if not config.enabled:
                return False, {}
            return True, config_repo.get_extra_config(scene)

    @staticmethod
    def _build_rare_card_content(
        account_name: str,
        set_code: str,
        pack_name: str,
        card_name: str,
        rarity_display: str,
        event_message: str,
        image_url: Optional[str] = None,
    ) -> str:
        """构建稀有卡牌通知正文。"""
        lines = [
            f"账号: {account_name}",
            f"事件: {event_message}",
        ]
        if set_code:
            lines.append(f"系列: {set_code}")
        if pack_name:
            lines.append(f"子包: {pack_name}")
        lines.append(f"卡牌: {card_name}")
        lines.append(f"稀有度: {rarity_display}")
        content = "\n".join(lines)
        if image_url:
            content += f"\n\n![{card_name}]({image_url})"
        return content

    def notify_rare_card_data(
        self,
        *,
        account_id: int | None,
        account_name: str,
        card_id: int,
        card_name: str,
        card_data: str | None,
        set_code: str,
        card_number: int,
        rarity: str,
        pack_name: str = "",
        image_url: Optional[str] = None,
        message: Optional[str] = None,
    ) -> bool:
        """使用纯数据发送稀有卡通知。"""
        enabled, extra_config = self._load_scene_extra_config(SCENE_RARE_CARD)
        if not enabled:
            return False
        notify_by_rarity = extra_config.get("notify_by_rarity", [])
        notify_card_ids = extra_config.get("notify_card_ids", [])

        # 内联 _is_rare_card_notifiable 判断
        if not (card_id in notify_card_ids or rarity in notify_by_rarity):
            logger.debug(f"卡牌 {card_name} ({rarity}) 不符合通知条件")
            return False

        web_lang = TASK_LOCALE_TO_WEB_LANG.get(DEFAULT_LOCALE, "zh_CN")
        rarity_display = get_rarity_display(rarity, web_lang)
        card_display_name = resolve_localized_text(
            raw_data=card_data,
            web_lang=web_lang,
            fallback=card_name,
            localized_field="localized_name",
        )

        title = "稀有卡牌通知"
        resolved_image_url = image_url or build_card_cdn_image_url(
            set_code=set_code,
            card_number=card_number,
            lang=web_lang,
            ext="png",
        )
        content = self._build_rare_card_content(
            account_name=account_name,
            set_code=set_code,
            pack_name=pack_name,
            card_name=card_display_name,
            rarity_display=rarity_display,
            event_message=message or "开出稀有卡牌",
            image_url=resolved_image_url,
        )

        return self.notify(
            scene=SCENE_RARE_CARD,
            title=title,
            content=content,
            account_id=account_id,
            card_id=card_id,
            image_url=resolved_image_url,
        )

    def notify_task_status(
        self,
        task_instance: "TaskInstance",
        status: str,
        message: str,
        account: TaskStatusAccount,
    ) -> bool:
        """
        任务状态通知

        Args:
            task_instance: 任务实例
            status: 状态（failed/blocked/timeout/success）
            message: 状态消息
            account: 账号快照；通知内容只依赖显式传入的账号上下文

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

        # 内联 _is_task_status_notifiable 判断
        if notify_task_types and task_type not in notify_task_types:
            logger.debug(f"任务类型 {task_type} 不在通知列表中")
            return False
        if status not in notify_on:
            logger.debug(f"状态 {status} 不在通知条件中")
            return False

        account_name = self._resolve_account_name(account)

        status_text = TASK_STATUS_TEXT_MAP.get(status, status)
        now_text = datetime.now().strftime("%Y-%m-%d %H:%M:%S")  # 内联 _format_now

        title = "任务状态通知"
        content = (
            f"账号: {account_name}\n"
            f"任务: {task_type}\n"
            f"状态: {status_text}\n"
            f"原因: {message}\n"
            f"时间: {now_text}"
        )

        return self.notify(
            scene=SCENE_TASK_STATUS,
            title=title,
            content=content,
            account_id=account.id,
            task_instance_id=task_instance.id,
        )

    def send_webhook_notification(
        self,
        title: str,
        content: str,
    ) -> bool:
        """直接发送指定通知内容到企业微信（不落库）。"""
        return self._send_webhook(title=title, content=content)

    def _send_webhook(
        self,
        title: str,
        content: str,
    ) -> bool:
        """
        发送企微 Webhook

        Args:
            title: 标题
            content: Markdown 内容

        Returns:
            是否发送成功
        """
        if not self.webhook_url:
            logger.warning("Webhook URL 未配置，跳过推送")
            return False

        payload = self._build_webhook_payload(
            title=title,
            content=content,
        )

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

    @staticmethod
    def _build_webhook_payload(
        title: str,
        content: str,
    ) -> dict:
        """构造企业微信 Webhook 载荷。"""
        markdown_content = f"## {title}\n\n{content}"

        return {
            "msgtype": "markdown_v2",
            "markdown_v2": {"content": markdown_content},
        }


_notifier_instance: Optional[Notifier] = None


def get_notifier() -> Notifier:
    """获取全局 Notifier 实例"""
    global _notifier_instance
    if _notifier_instance is None:
        _notifier_instance = Notifier()
    return _notifier_instance
