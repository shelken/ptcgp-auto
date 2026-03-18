# -*- coding: utf-8 -*-
"""
通知记录 Repository

提供通知记录的数据访问方法。
"""

from datetime import datetime
from typing import List, Optional

from sqlmodel import col, func, select

from ptcgp_auto_v2.db.models import Notification
from .base import BaseRepository


class NotificationRepository(BaseRepository):
    """通知记录数据访问层"""

    def create(
        self,
        scene: str,
        title: str,
        content: str,
        account_id: Optional[int] = None,
        card_id: Optional[int] = None,
        task_instance_id: Optional[int] = None,
    ) -> Notification:
        """创建通知记录"""
        notification = Notification(
            scene=scene,
            title=title,
            content=content,
            related_account_id=account_id,
            related_card_id=card_id,
            related_task_instance_id=task_instance_id,
        )
        self.session.add(notification)
        self._finish_write(notification)
        return notification

    def get_by_id(self, notification_id: int) -> Optional[Notification]:
        """根据 ID 获取通知"""
        return self.session.get(Notification, notification_id)

    def list(
        self,
        scene: Optional[str] = None,
        account_id: Optional[int] = None,
        is_read: Optional[bool] = None,
        page: int = 0,
        page_size: int = 20,
    ) -> List[Notification]:
        """列表查询通知"""
        statement = select(Notification)
        if scene:
            statement = statement.where(Notification.scene == scene)
        if account_id is not None:
            statement = statement.where(Notification.related_account_id == account_id)
        if is_read is not None:
            statement = statement.where(Notification.is_read == is_read)
        statement = statement.order_by(col(Notification.created_at).desc())
        statement = statement.offset(page * page_size).limit(page_size)
        return list(self.session.exec(statement).all())

    def count(
        self,
        scene: Optional[str] = None,
        account_id: Optional[int] = None,
        is_read: Optional[bool] = None,
    ) -> int:
        """统计通知数量"""
        statement = select(func.count()).select_from(Notification)
        if scene:
            statement = statement.where(Notification.scene == scene)
        if account_id is not None:
            statement = statement.where(Notification.related_account_id == account_id)
        if is_read is not None:
            statement = statement.where(Notification.is_read == is_read)
        result = self.session.exec(statement).one()
        return result or 0

    def count_unread(self) -> int:
        """统计未读通知数量"""
        return self.count(is_read=False)

    def mark_as_read(self, notification_id: int) -> bool:
        """标记单条通知为已读"""
        notification = self.session.get(Notification, notification_id)
        if not notification:
            return False
        notification.is_read = True
        self.session.add(notification)
        self._finish_write(notification)
        return True

    def mark_all_as_read(
        self,
        scene: Optional[str] = None,
        account_id: Optional[int] = None,
    ) -> int:
        """批量标记已读"""
        statement = select(Notification).where(Notification.is_read == False)  # noqa: E712
        if scene:
            statement = statement.where(Notification.scene == scene)
        if account_id is not None:
            statement = statement.where(Notification.related_account_id == account_id)
        notifications = self.session.exec(statement).all()
        count = 0
        for notification in notifications:
            notification.is_read = True
            self.session.add(notification)
            count += 1
        self._finish_write(*notifications)
        return count

    def delete(self, notification_id: int) -> bool:
        """删除通知"""
        notification = self.session.get(Notification, notification_id)
        if notification:
            self.session.delete(notification)
            self._finish_write()
            return True
        return False

    def delete_old_notifications(self, days: int = 30) -> int:
        """删除超过指定天数的已读通知"""
        threshold = datetime.now().timestamp() - days * 24 * 60 * 60
        threshold_dt = datetime.fromtimestamp(threshold)
        statement = select(Notification).where(
            Notification.is_read == True,  # noqa: E712
            Notification.created_at < threshold_dt,
        )
        notifications = self.session.exec(statement).all()
        count = 0
        for notification in notifications:
            self.session.delete(notification)
            count += 1
        self._finish_write()
        return count
