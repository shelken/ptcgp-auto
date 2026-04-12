# -*- coding: utf-8 -*-
"""Hook 模块导出"""

from .friend_hooks import (
    DeleteFriendPostHook as DeleteFriendPostHook,
    FriendPreHook as FriendPreHook,
    ManageFriendshipWakePostHook as ManageFriendshipWakePostHook,
)
from .exchange_hooks import ExchangeDelayPostHook as ExchangeDelayPostHook
from .gift_hooks import SendCardWakeTargetPostHook as SendCardWakeTargetPostHook
from .gift_hooks import ClaimGiftsPreHook as ClaimGiftsPreHook
