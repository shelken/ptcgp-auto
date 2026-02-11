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
