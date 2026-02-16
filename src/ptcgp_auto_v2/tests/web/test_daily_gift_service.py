# -*- coding: utf-8 -*-

from ptcgp_auto_v2.web.services import daily_gift_service


def test_normalize_biz_date_should_fallback_to_game_biz_date(monkeypatch):
    monkeypatch.setattr(
        daily_gift_service,
        "get_game_biz_date_str",
        lambda: "2026-02-15",
        raising=False,
    )

    assert daily_gift_service._normalize_biz_date_local(None) == "2026-02-15"
    assert daily_gift_service._normalize_biz_date_local("invalid") == "2026-02-15"


def test_build_recent_dates_should_include_selected_day_first():
    assert daily_gift_service._build_recent_dates("2026-02-16", days=2) == [
        "2026-02-16",
        "2026-02-15",
        "2026-02-14",
    ]
