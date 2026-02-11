# -*- coding: utf-8 -*-
"""Hook 模块导出"""

from .friend_hooks import (
    DeleteFriendPostHook,
    FriendPreHook,
    ManageFriendshipWakePostHook,
)
from .gift_hooks import SendCardWakeTargetPostHook
from .gift_hooks import ClaimGiftsPreHook

__all__ = [
    "FriendPreHook",
    "DeleteFriendPostHook",
    "ManageFriendshipWakePostHook",
    "ClaimGiftsPreHook",
    "SendCardWakeTargetPostHook",
]
