# -*- coding: utf-8 -*-
"""compute_next_run_at 单元测试 - 过去时间返回 None（立即执行）。"""

from datetime import datetime

from ptcgp_auto_v2.core.scheduling_service import compute_next_run_at


class TestComputeNextRunAtPastReturnsNone:
    """算出的时间为过去时返回 None，表示立即可执行。"""

    @staticmethod
    def test_interval_past_returns_none():
        """interval 用旧锚点计算得出过去时间 → None。"""
        now = datetime(2026, 5, 26, 12, 0, 0)
        last = datetime(2026, 3, 18, 11, 44, 41)
        result = compute_next_run_at(
            last, "interval", {"interval_seconds": 86400}, now=now
        )
        assert result is None

    @staticmethod
    def test_daily_past_returns_none():
        """daily 用旧锚点计算得出过去时间 → None。"""
        now = datetime(2026, 5, 26, 12, 0, 0)
        last = datetime(2026, 3, 18, 11, 44, 41)
        result = compute_next_run_at(last, "daily", now=now)
        assert result is None

    @staticmethod
    def test_weekly_past_returns_none():
        """weekly 用旧锚点计算得出过去时间 → None。"""
        now = datetime(2026, 5, 26, 12, 0, 0)
        last = datetime(2026, 3, 18, 11, 44, 41)
        result = compute_next_run_at(last, "weekly", now=now)
        assert result is None

    @staticmethod
    def test_interval_future_still_returns_time():
        """interval 锚点在当前之后 → 返回未来时间。"""
        now = datetime(2026, 5, 26, 12, 0, 0)
        last = datetime(2026, 5, 26, 10, 0, 0)
        result = compute_next_run_at(
            last, "interval", {"interval_seconds": 86400}, now=now
        )
        assert result == datetime(2026, 5, 27, 10, 0, 0)

    @staticmethod
    def test_last_completed_none_returns_none():
        """last_completed 为 None → None。"""
        result = compute_next_run_at(None, "daily")
        assert result is None

    @staticmethod
    def test_once_returns_none():
        """once 类型 → None（原有行为）。"""
        result = compute_next_run_at(datetime.now(), "once")
        assert result is None, "once 类型应始终返回 None"
