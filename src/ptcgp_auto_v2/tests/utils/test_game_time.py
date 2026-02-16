# -*- coding: utf-8 -*-

from datetime import datetime

from ptcgp_auto_v2.utils.game_time import get_game_biz_date_str, get_game_day_window
import ptcgp_auto_v2.utils.game_time as game_time


def test_get_game_biz_date_str_before_14_should_use_previous_day():
    now = datetime(2026, 2, 16, 12, 0, 0)
    assert get_game_biz_date_str(now) == "2026-02-15"


def test_get_game_biz_date_str_at_14_should_use_same_day():
    now = datetime(2026, 2, 16, 14, 0, 0)
    assert get_game_biz_date_str(now) == "2026-02-16"


def test_get_game_day_window_before_14_should_start_previous_day_14():
    now = datetime(2026, 2, 16, 13, 0, 0)
    start, end = get_game_day_window(now)
    assert start == datetime(2026, 2, 15, 14, 0, 0)
    assert end == datetime(2026, 2, 16, 14, 0, 0)


def test_get_game_day_window_after_14_should_start_same_day_14():
    now = datetime(2026, 2, 16, 23, 0, 0)
    start, end = get_game_day_window(now)
    assert start == datetime(2026, 2, 16, 14, 0, 0)
    assert end == datetime(2026, 2, 17, 14, 0, 0)


def test_get_game_biz_date_str_should_follow_configured_utc_offset(monkeypatch):
    monkeypatch.setattr(game_time, "GAME_UTC_OFFSET_HOURS", -8)
    assert (
        game_time.get_game_biz_date_str(datetime(2026, 2, 16, 21, 0, 0)) == "2026-02-15"
    )
    assert (
        game_time.get_game_biz_date_str(datetime(2026, 2, 16, 22, 0, 0)) == "2026-02-16"
    )
