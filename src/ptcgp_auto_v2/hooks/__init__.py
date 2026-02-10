# -*- coding: utf-8 -*-
"""Hook 模块导出"""

from .friend_hooks import DeleteFriendPostHook, FriendPreHook

__all__ = [
    "FriendPreHook",
    "DeleteFriendPostHook",
]
