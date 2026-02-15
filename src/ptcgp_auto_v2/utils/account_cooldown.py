# -*- coding: utf-8 -*-
"""
账号功能冷冻期判断工具。
"""

from datetime import datetime, timedelta
from typing import Optional


def is_account_past_days(created_at: Optional[datetime], days: int) -> bool:
    """判断账号创建时间是否已超过指定天数。"""
    if created_at is None:
        return False
    threshold = datetime.now() - timedelta(days=days)
    return created_at <= threshold


def is_account_pending_same_day_cooldown(
    created_at: Optional[datetime], days: int
) -> bool:
    """判断账号是否同日待过冷冻期（未到时间但到期日与今天相同）。"""
    if created_at is None:
        return False
    if not isinstance(days, int):
        return False
    cooldown_at = created_at + timedelta(days=days)
    now = datetime.now()
    return now < cooldown_at and now.date() == cooldown_at.date()
