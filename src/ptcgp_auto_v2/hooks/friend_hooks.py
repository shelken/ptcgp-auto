# -*- coding: utf-8 -*-
"""
好友关系 Hook

包含前置检查与后置删除逻辑。
"""

from typing import Optional

from ptcgp_auto_v2.core.hooks import Hook, HookContext, HookResult
from ptcgp_auto_v2.db.repositories import FriendRequestRepository
from ptcgp_auto_v2.services.friendship_service import FriendshipService


class FriendPreHook(Hook):
    """
    好友关系前置检查 Hook

    在需要好友关系的任务前检查是否已是指定账号的好友。
    如果不是，创建添加好友请求并触发 ManageFriendshipTask。
    """

    def __init__(self, target_friend_id: str, target_account_id: Optional[int] = None):
        """初始化前置 Hook"""
        self.target_friend_id = target_friend_id
        self.target_account_id = target_account_id

    def run(self, context: HookContext) -> tuple[HookResult, dict]:
        """执行前置检查"""
        is_friend = FriendshipService.is_friend(
            account_id=context.account.id,
            friend_id=self.target_friend_id,
        )

        if is_friend:
            return HookResult.CONTINUE, {}

        existing = FriendRequestRepository().get_pending_request(
            from_account_id=context.account.id,
            to_friend_id=self.target_friend_id,
        )

        if existing:
            return HookResult.INSERT_TASK, {
                "task_type": "manage_friendship",
                "priority": "high",
                "reason": "已有好友请求待处理",
            }

        FriendshipService.create_add_request(
            from_account_id=context.account.id,
            to_friend_id=self.target_friend_id,
            to_account_id=self.target_account_id,
        )

        return HookResult.INSERT_TASK, {
            "task_type": "manage_friendship",
            "priority": "high",
            "reason": "需要建立好友关系",
        }


class DeleteFriendPostHook(Hook):
    """
    删除好友后置 Hook

    在任务完成后删除好友。
    用于送卡任务完成后清理好友关系。
    """

    def __init__(self, target_friend_id: str):
        """初始化后置 Hook"""
        self.target_friend_id = target_friend_id

    def run(self, context: HookContext) -> tuple[HookResult, dict]:
        """执行后置删除"""
        FriendshipService.create_delete_request(
            account_id=context.account.id,
            friend_id=self.target_friend_id,
        )

        return HookResult.CONTINUE, {}


class ManageFriendshipWakePostHook(Hook):
    """好友任务后置唤醒 Hook。"""

    def run(self, context: HookContext) -> tuple[HookResult, dict]:
        """在任务结束后统一唤醒目标账号的 manage_friendship 任务。"""
        wake_account_ids = getattr(context.task, "_wake_account_ids", set())
        for account_id in wake_account_ids:
            FriendshipService.ensure_manage_friendship_pending(account_id=account_id)
        return HookResult.CONTINUE, {}
