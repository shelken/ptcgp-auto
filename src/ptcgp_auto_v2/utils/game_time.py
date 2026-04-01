# -*- coding: utf-8 -*-
"""
游戏业务时间工具。

统一定义“游戏日”边界：游戏固定 UTC 06:00 刷新。
本地刷新时刻由 UTC 偏移小时数自动换算。
"""

from __future__ import annotations

from datetime import datetime, time, timedelta, timezone

from ptcgp_auto_v2.config.constants import GAME_UTC_OFFSET_HOURS

GAME_RESET_UTC_HOUR = 6
GAME_RESET_UTC_MINUTE = 0


def _to_game_timezone(now: datetime | None = None) -> datetime:
    """将输入时间转换到配置偏移对应的本地时区时间。"""
    tz = timezone(timedelta(hours=GAME_UTC_OFFSET_HOURS))
    if now is None:
        return datetime.now(timezone.utc).astimezone(tz)
    if now.tzinfo is None:
        return now.replace(tzinfo=tz)
    return now.astimezone(tz)


def get_game_day_window(now: datetime | None = None) -> tuple[datetime, datetime]:
    """返回当前游戏日时间窗口 [start, end)，使用配置偏移的本地时钟值。"""
    game_now = _to_game_timezone(now)
    reset_hour = (GAME_RESET_UTC_HOUR + GAME_UTC_OFFSET_HOURS) % 24
    reset_time = time(hour=reset_hour, minute=GAME_RESET_UTC_MINUTE)
    day = game_now.date()
    if game_now.time() < reset_time:
        day = day - timedelta(days=1)

    start = datetime.combine(day, reset_time)
    end = start + timedelta(days=1)
    return start, end


def get_next_game_day_reset_at(now: datetime | None = None) -> datetime:
    """返回给定时间所在游戏日的下一次刷新时刻。"""
    _, end = get_game_day_window(now)
    return end


def has_game_day_rolled_over(
    anchor: datetime,
    now: datetime | None = None,
) -> bool:
    """判断给定锚点所在游戏日是否已经切换。"""
    anchor_start, _ = get_game_day_window(anchor)
    current_start, _ = get_game_day_window(now)
    return anchor_start < current_start


def get_game_biz_date_str(now: datetime | None = None) -> str:
    """返回当前游戏业务日期（YYYY-MM-DD）。"""
    start, _ = get_game_day_window(now)
    return start.strftime("%Y-%m-%d")
