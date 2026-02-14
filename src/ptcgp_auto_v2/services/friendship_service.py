# -*- coding: utf-8 -*-
"""
好友关系服务

提供对外的好友请求/关系管理接口。
"""

from typing import Optional, TYPE_CHECKING
from datetime import datetime

from ptcgp_auto_v2.db.repositories import (
    AccountRepository,
    FriendRequestRepository,
    FriendshipRepository,
    TaskInstanceRepository,
)
from ptcgp_auto_v2.core.task_status import TaskStatus

if TYPE_CHECKING:
    from ptcgp_auto_v2.db.models import AccountFriendRequest


class FriendshipService:
    """
    好友关系服务

    供 Hook 和外部任务调用的开放接口。
    通过创建数据库记录 + 触发 TaskInstance 来实现任务调度。
    """

    @staticmethod
    def create_add_request(
        from_account_id: int,
        to_friend_id: str,
        to_account_id: Optional[int] = None,
        to_nickname: Optional[str] = None,
    ) -> "AccountFriendRequest | None":
        """
        创建添加好友请求

        用于 FriendPreHook 或其他任务需要建立好友关系时调用。
        """
        normalized_friend_id = "".join(ch for ch in to_friend_id if ch.isdigit())
        if not normalized_friend_id:
            return None

        if to_account_id is not None and int(to_account_id) == int(from_account_id):
            return None

        account_repo = AccountRepository()
        from_account = account_repo.get_by_id(from_account_id)
        if from_account is None:
            return None

        if from_account.friend_id == normalized_friend_id:
            return None

        # 系统账号目标也要做自环校验（兜底，避免脏表单）
        if to_account_id is not None:
            target_account = account_repo.get_by_id(to_account_id)
            if target_account is None:
                return None
            if target_account.id == from_account.id:
                return None
            if (
                target_account.friend_id
                and target_account.friend_id == from_account.friend_id
            ):
                return None

        # 已是好友不应继续创建 add 请求
        if FriendshipRepository().exists(
            account_id=from_account_id,
            friend_id=normalized_friend_id,
        ):
            return None

        # 待处理 add 请求去重（sending/sended）
        if FriendRequestRepository().has_pending_add_request(
            from_account_id=from_account_id,
            to_friend_id=normalized_friend_id,
        ):
            return None

        request = FriendRequestRepository().create(
            from_account_id=from_account_id,
            to_friend_id=normalized_friend_id,
            to_account_id=to_account_id,
            to_nickname=to_nickname,
            request_type="add",
            status="sending",
        )

        FriendshipService.ensure_manage_friendship_pending(account_id=from_account_id)

        return request

    @staticmethod
    def create_delete_request(
        account_id: int,
        friend_id: str,
        to_account_id: Optional[int] = None,
    ) -> "AccountFriendRequest | None":
        """
        创建删除好友请求

        PostHook 场景下应先更新 friendship 表记录，再触发同步删除任务。
        """
        normalized_friend_id = "".join(ch for ch in friend_id if ch.isdigit())
        if not normalized_friend_id:
            return None

        account = AccountRepository().get_by_id(account_id)
        if account is None:
            return None

        if account.friend_id == normalized_friend_id:
            return None

        if FriendRequestRepository().has_pending_delete_request(
            from_account_id=account_id,
            to_friend_id=normalized_friend_id,
        ):
            return None

        friendship_repo = FriendshipRepository()
        friendship = friendship_repo.get_friendship(
            account_id=account_id,
            friend_id=normalized_friend_id,
        )
        if friendship is None:
            return None

        resolved_to_account_id = to_account_id
        if resolved_to_account_id is None:
            resolved_to_account_id = friendship.friend_account_id

        friendship_repo.remove_friendship(
            account_id=account_id,
            friend_id=normalized_friend_id,
        )

        request = FriendRequestRepository().create(
            from_account_id=account_id,
            to_friend_id=normalized_friend_id,
            to_account_id=resolved_to_account_id,
            request_type="delete",
            status="deleting",
        )

        FriendshipService.ensure_manage_friendship_pending(account_id=account_id)

        return request

    @staticmethod
    def is_friend(account_id: int, friend_id: str) -> bool:
        """检查是否是好友"""
        return FriendshipRepository().exists(
            account_id=account_id,
            friend_id=friend_id,
        )

    @staticmethod
    def cancel_request(request_id: int) -> bool:
        """取消待处理请求：sended 的 add 转为 canceling，其余待处理记录直接删除。"""
        repo = FriendRequestRepository()
        request = repo.get_by_id(request_id)
        if request is None:
            return False

        if request.request_type == "add" and request.status == "sended":
            request.status = "canceling"
            request.failed_reason = None
            request.updated_at = datetime.now()
            repo.update(request)
            FriendshipService.ensure_manage_friendship_pending(
                account_id=request.from_account_id
            )
            return True

        return repo.delete_pending(request_id=request_id)

    @staticmethod
    def ensure_manage_friendship_pending(account_id: int) -> bool:
        """确保账号的 manage_friendship 任务处于 pending（不存在则创建）。"""
        repo = TaskInstanceRepository()
        instance = repo.get_by_account_and_type(account_id, "manage_friendship")

        if instance is None:
            instance = repo.get_or_create(
                account_id=account_id,
                task_type="manage_friendship",
                reset_type="once",
            )

        if instance.status != TaskStatus.PENDING.value:
            instance.status = TaskStatus.PENDING.value
            instance.next_run_at = None
            instance.save()

        return True
