# -*- coding: utf-8 -*-
"""
好友关系 Hook

包含前置检查与后置删除逻辑。
"""

from typing import Optional

from ptcgp_auto_v2.core.hooks import Hook, HookContext, HookResult
from ptcgp_auto_v2.db.repositories import FriendRequestRepository
from ptcgp_auto_v2.services.friendship_service import FriendshipService

INTERNAL_SENDED_DELAY_SECONDS = 180
EXTERNAL_SENDED_DELAY_SECONDS = 600


class FriendPreHook(Hook):
    """
    好友关系前置检查 Hook

    在需要好友关系的任务前检查是否已是指定账号的好友。
    如果不是，创建添加好友请求并触发 ManageFriendshipTask。
    """

    def __init__(
        self,
        target_friend_id: str,
        target_account_id: Optional[int] = None,
        target_nickname: Optional[str] = None,
    ):
        """初始化前置 Hook"""
        self.target_friend_id = target_friend_id
        self.target_account_id = target_account_id
        self.target_nickname = target_nickname

    def run(self, context: HookContext) -> tuple[HookResult, dict]:
        """
        执行前置检查

        三种场景：
        1. 无请求 → 创建请求 + INSERT_TASK
        2. 请求 status=sending → INSERT_TASK（还没发送）
        3. 请求 status=sended（系统内）→ 唤醒对方账号 + DELAY（延后重试原任务）
        4. 请求 status=sended（外部）→ 触发本账号检查 + DELAY（延后重试原任务）
        """
        if context.account.id is None:
            return HookResult.ABORT, {"error": "账号ID为空"}
        account_id = int(context.account.id)

        is_friend = FriendshipService.is_friend(
            account_id=account_id,
            friend_id=self.target_friend_id,
        )

        if is_friend:
            return HookResult.CONTINUE, {}

        existing = FriendRequestRepository().get_pending_request(
            from_account_id=account_id,
            to_friend_id=self.target_friend_id,
        )

        if existing is None:
            # 场景1：无请求，创建并发送
            FriendshipService.create_add_request(
                from_account_id=account_id,
                to_friend_id=self.target_friend_id,
                to_account_id=self.target_account_id,
                to_nickname=self.target_nickname,
            )
            return HookResult.INSERT_TASK, {
                "task_type": "manage_friendship",
                "priority": "high",
                "reason": "需要建立好友关系",
            }

        if existing.status == "sending":
            # 场景2：请求存在但还没发送
            return HookResult.INSERT_TASK, {
                "task_type": "manage_friendship",
                "priority": "high",
                "reason": "好友请求待发送",
            }

        if existing.status == "sended":
            if existing.to_account_id:
                # 场景3：系统内好友，已发送，等待对方接受
                FriendshipService.ensure_manage_friendship_pending(
                    account_id=existing.to_account_id
                )
                return HookResult.DELAY, {
                    "delay_seconds": INTERNAL_SENDED_DELAY_SECONDS,
                    "reason": "等待对方接受好友请求",
                }
            else:
                # 场景4：外部好友，已发送，触发本账号检查确认
                FriendshipService.ensure_manage_friendship_pending(
                    account_id=account_id
                )
                return HookResult.DELAY, {
                    "delay_seconds": EXTERNAL_SENDED_DELAY_SECONDS,
                    "reason": "等待外部好友接受请求",
                }

        # 其他状态（completed/failed/canceled），重新创建请求
        FriendshipService.create_add_request(
            from_account_id=account_id,
            to_friend_id=self.target_friend_id,
            to_account_id=self.target_account_id,
            to_nickname=self.target_nickname,
        )
        return HookResult.INSERT_TASK, {
            "task_type": "manage_friendship",
            "priority": "high",
            "reason": "需要重新建立好友关系",
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
        if context.account.id is None:
            return HookResult.CONTINUE, {}
        account_id = int(context.account.id)

        FriendshipService.create_delete_request(
            account_id=account_id,
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
