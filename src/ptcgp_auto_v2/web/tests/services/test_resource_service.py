# -*- coding: utf-8 -*-

from ptcgp_auto_v2.web.services.resource_service import build_resources_context


def test_build_resources_context_should_fallback_to_stats_for_default_or_invalid_view(
    session, monkeypatch
):
    """默认或非法视图都应回退到 stats。"""

    stats_result = ([{"account_id": 1}], 1)

    def fake_list_account_resources(**kwargs):
        return stats_result

    monkeypatch.setattr(
        "ptcgp_auto_v2.web.services.resource_service.list_account_resources",
        fake_list_account_resources,
    )
    monkeypatch.setattr(
        "ptcgp_auto_v2.web.services.resource_service.list_pack_point_resources",
        lambda **_kwargs: {"rows": [], "total": 0, "series_list": []},
    )

    default_context = build_resources_context(session=session)
    invalid_context = build_resources_context(session=session, view="invalid")

    assert default_context["view"] == "stats"
    assert default_context["items"] == stats_result[0]
    assert invalid_context["view"] == "stats"
    assert invalid_context["items"] == stats_result[0]


def test_build_resources_context_should_pass_through_stats_result(session, monkeypatch):
    """stats 视图应透传资源条目、分页状态与总数。"""

    captured_kwargs = {}

    def fake_list_account_resources(**kwargs):
        captured_kwargs.update(kwargs)
        return ([{"account_id": 9, "exchange_points": 12}], 21)

    monkeypatch.setattr(
        "ptcgp_auto_v2.web.services.resource_service.list_account_resources",
        fake_list_account_resources,
    )
    monkeypatch.setattr(
        "ptcgp_auto_v2.web.services.resource_service.list_pack_point_resources",
        lambda **_kwargs: {"rows": [], "total": 0, "series_list": []},
    )

    context = build_resources_context(
        session=session,
        view="stats",
        q="Pika",
        sort_by="exchange_points",
        sort_order="desc",
        page=1,
        page_size=10,
    )

    assert captured_kwargs == {
        "session": session,
        "q": "Pika",
        "sort_by": "exchange_points",
        "sort_order": "desc",
        "page": 1,
        "page_size": 10,
    }
    assert context == {
        "view": "stats",
        "items": [{"account_id": 9, "exchange_points": 12}],
        "q": "Pika",
        "sort_by": "exchange_points",
        "sort_order": "desc",
        "page": 1,
        "page_size": 10,
        "has_prev": True,
        "has_next": True,
        "total": 21,
        "series_list": [],
    }


def test_build_resources_context_should_pass_through_pack_points_result(
    session, monkeypatch
):
    """pack-points 视图应透传 rows 与 series_list。"""

    captured_kwargs = {}

    def fake_list_pack_point_resources(**kwargs):
        captured_kwargs.update(kwargs)
        return {
            "rows": [{"account_id": 3, "series_points": {"A1": 120}}],
            "total": 1,
            "series_list": ["A1", "A2"],
        }

    monkeypatch.setattr(
        "ptcgp_auto_v2.web.services.resource_service.list_account_resources",
        lambda **_kwargs: ([], 0),
    )
    monkeypatch.setattr(
        "ptcgp_auto_v2.web.services.resource_service.list_pack_point_resources",
        fake_list_pack_point_resources,
    )

    context = build_resources_context(
        session=session,
        view="pack-points",
        q="friend",
        sort_by="series:A1",
        sort_order="asc",
        page=0,
        page_size=5,
    )

    assert captured_kwargs == {
        "session": session,
        "q": "friend",
        "sort_by": "series:A1",
        "sort_order": "asc",
        "page": 0,
        "page_size": 5,
    }
    assert context == {
        "view": "pack-points",
        "items": [{"account_id": 3, "series_points": {"A1": 120}}],
        "q": "friend",
        "sort_by": "series:A1",
        "sort_order": "asc",
        "page": 0,
        "page_size": 5,
        "has_prev": False,
        "has_next": False,
        "total": 1,
        "series_list": ["A1", "A2"],
    }


def test_build_resources_context_should_reset_invalid_sort_for_pack_points(
    session, monkeypatch
):
    """pack-points 视图收到 stats 排序字段时应重置为 id。"""

    captured_kwargs = {}

    def fake_list_pack_point_resources(**kwargs):
        captured_kwargs.update(kwargs)
        return {"rows": [], "total": 0, "series_list": []}

    monkeypatch.setattr(
        "ptcgp_auto_v2.web.services.resource_service.list_account_resources",
        lambda **_kwargs: ([], 0),
    )
    monkeypatch.setattr(
        "ptcgp_auto_v2.web.services.resource_service.list_pack_point_resources",
        fake_list_pack_point_resources,
    )

    context = build_resources_context(
        session=session,
        view="pack-points",
        sort_by="exchange_points",
    )

    assert captured_kwargs["sort_by"] == "id"
    assert context["sort_by"] == "id"


def test_build_resources_context_should_reset_invalid_sort_for_stats(
    session, monkeypatch
):
    """stats 视图收到系列排序字段时应重置为 id。"""

    captured_kwargs = {}

    def fake_list_account_resources(**kwargs):
        captured_kwargs.update(kwargs)
        return ([], 0)

    monkeypatch.setattr(
        "ptcgp_auto_v2.web.services.resource_service.list_account_resources",
        fake_list_account_resources,
    )
    monkeypatch.setattr(
        "ptcgp_auto_v2.web.services.resource_service.list_pack_point_resources",
        lambda **_kwargs: {"rows": [], "total": 0, "series_list": []},
    )

    context = build_resources_context(
        session=session,
        view="stats",
        sort_by="series:A1",
    )

    assert captured_kwargs["sort_by"] == "id"
    assert context["sort_by"] == "id"
