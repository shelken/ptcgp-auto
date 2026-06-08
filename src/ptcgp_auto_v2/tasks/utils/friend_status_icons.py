# -*- coding: utf-8 -*-
"""好友状态图标识别 helper。"""

from dataclasses import dataclass
from typing import Any

FRIEND_STATUS_GREEN_YES_TEMPLATE = "icon_green_yes"
FRIEND_STATUS_RED_NO_TEMPLATE = "icon_red_no"
FRIEND_STATUS_TEMPLATE_THRESHOLD = 0.8
FRIEND_STATUS_TEMPLATE_SCALES = (1.0, 0.8)


@dataclass(frozen=True)
class FriendIconStatus:
    """好友绿色勾/红色叉在固定 scale 下的模板命中结果。"""

    green_1x: Any | None
    red_1x: Any | None
    green_08: Any | None
    red_08: Any | None

    @property
    def is_pending_reply(self) -> bool:
        """1.0 绿色勾和 1.0 红色叉同时命中。"""
        return self.green_1x is not None and self.red_1x is not None

    @property
    def is_already_friend(self) -> bool:
        """0.8 绿色勾命中。"""
        return self.green_08 is not None

    @property
    def is_friend_confirmed(self) -> bool:
        """任意绿色勾命中，且任意红色叉都未命中。"""
        has_green = self.green_1x is not None or self.green_08 is not None
        has_red = self.red_1x is not None or self.red_08 is not None
        return has_green and not has_red

    @property
    def has_green_and_red(self) -> bool:
        """任意绿色勾和任意红色叉同时命中。"""
        has_green = self.green_1x is not None or self.green_08 is not None
        has_red = self.red_1x is not None or self.red_08 is not None
        return has_green and has_red


def friend_status_by_icons(page_detector) -> FriendIconStatus:
    """一次读取好友状态相关图标，避免各状态分散维护模板参数。"""
    # 变更原因：scale 差异是历史有意语义，集中配置但不合并状态判定。
    green_1x = page_detector.find_template_with_scale(
        FRIEND_STATUS_GREEN_YES_TEMPLATE,
        scale=FRIEND_STATUS_TEMPLATE_SCALES[0],
        threshold=FRIEND_STATUS_TEMPLATE_THRESHOLD,
    )
    red_1x = page_detector.find_template_with_scale(
        FRIEND_STATUS_RED_NO_TEMPLATE,
        scale=FRIEND_STATUS_TEMPLATE_SCALES[0],
        threshold=FRIEND_STATUS_TEMPLATE_THRESHOLD,
    )
    green_08 = page_detector.find_template_with_scale(
        FRIEND_STATUS_GREEN_YES_TEMPLATE,
        scale=FRIEND_STATUS_TEMPLATE_SCALES[1],
        threshold=FRIEND_STATUS_TEMPLATE_THRESHOLD,
    )
    red_08 = page_detector.find_template_with_scale(
        FRIEND_STATUS_RED_NO_TEMPLATE,
        scale=FRIEND_STATUS_TEMPLATE_SCALES[1],
        threshold=FRIEND_STATUS_TEMPLATE_THRESHOLD,
    )
    return FriendIconStatus(
        green_1x=green_1x,
        red_1x=red_1x,
        green_08=green_08,
        red_08=red_08,
    )
