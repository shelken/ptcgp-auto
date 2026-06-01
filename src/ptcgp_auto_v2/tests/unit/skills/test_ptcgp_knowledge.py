# -*- coding: utf-8 -*-
"""ptcgp-knowledge skill 内置脚本测试。"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

SCRIPT_PATH = Path(__file__).resolve().parents[5] / ".agents" / "skills" / "ptcgp-knowledge" / "scripts" / "raenonx_events.py"
SPEC = importlib.util.spec_from_file_location("raenonx_events", SCRIPT_PATH)
assert SPEC is not None
rx_events = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(rx_events)

NOW = 1_800_000_000


def _event(
    event_type: str = "soloBattle",
    event_id: str = "EV_TEST",
    name_id: str | None = "2605000_01",
    start: int = NOW - 100,
    end: int = NOW + 100,
    extra: dict | None = None,
) -> dict:
    data = {
        "id": event_id,
        "nameI18nId": name_id,
        "timeframe": {"startEpoch": start, "endEpoch": end},
    }
    if extra:
        data.update(extra)
    return {"type": event_type, "data": data}


def test_classify_state_uses_current_upcoming_future_expired_and_permanent() -> None:
    assert rx_events.classify_state(NOW - 10, NOW + 10, NOW) == "current"
    assert rx_events.classify_state(NOW + 10, NOW + 100, NOW) == "upcoming"
    assert rx_events.classify_state(NOW + 31 * 24 * 60 * 60, NOW + 40 * 24 * 60 * 60, NOW) == "future"
    assert rx_events.classify_state(NOW - 100, NOW - 10, NOW) == "expired"
    assert rx_events.classify_state(NOW - 100, 0, NOW) == "permanent"


@pytest.mark.parametrize(("page", "limit", "error"), [(0, 20, "page"), (1, 0, "limit"), (1, 101, "limit")])
def test_validate_pagination_rejects_invalid_values(page: int, limit: int, error: str) -> None:
    with pytest.raises(ValueError, match=error):
        rx_events.validate_pagination(page, limit)


def test_normalize_event_resolves_name_rewards_and_related_cards() -> None:
    item = _event(
        extra={
            "products": [
                {
                    "contents": [
                        {"meta": {"type": "cardPack", "id": "BP001_0090_00_000"}, "count": 1},
                        {"meta": {"type": "card", "id": "PK_10_015280_00"}, "count": 1},
                    ]
                }
            ],
            "battleDataList": [
                {
                    "npcDeck": {
                        "highlights": ["PK_10_015280_00"],
                        "cards": ["TR_10_000100_00", "PK_10_015280_00"],
                    },
                    "clearRewards": [{"meta": {"type": "item", "id": "IT_TEST"}, "count": 3}],
                }
            ],
        },
    )

    result = rx_events.normalize_event(item, {"2605000_01": "蒼炎刃鬼ex掉落活動"}, NOW)

    assert result["name"] == "蒼炎刃鬼ex掉落活動"
    assert result["titleFallback"] == "蒼炎刃鬼ex掉落活動"
    assert result["state"] == "current"
    assert {reward["id"] for reward in result["rewardSummary"]} == {
        "BP001_0090_00_000",
        "PK_10_015280_00",
        "IT_TEST",
    }
    assert result["relatedCardIds"] == ["PK_10_015280_00", "TR_10_000100_00"]


def test_normalize_event_falls_back_when_name_missing() -> None:
    result = rx_events.normalize_event(_event(name_id=None), {}, NOW)

    assert result["name"] is None
    assert result["titleFallback"] == "EV_TEST"
    assert "missing nameI18nId" in result["warnings"]


def test_find_event_uses_type_and_id() -> None:
    events = [
        rx_events.normalize_event(_event("wonderPickFree", "SC_GC_2605000_01"), {}, NOW),
        rx_events.normalize_event(_event("wonderPickChansey", "SC_GC_2605000_01"), {}, NOW),
    ]

    result = rx_events.find_event(events, "wonderPickChansey", "SC_GC_2605000_01")

    assert result["type"] == "wonderPickChansey"


def test_paginate_returns_metadata_and_slice() -> None:
    events = [rx_events.normalize_event(_event(event_id=f"EV_{i}"), {}, NOW) for i in range(5)]

    page = rx_events.paginate(events, page=2, limit=2)

    assert page["page"] == 2
    assert page["limit"] == 2
    assert page["total"] == 5
    assert [item["id"] for item in page["items"]] == ["EV_2", "EV_3"]


def test_extract_messages_from_rsc_decodes_json_string_pairs() -> None:
    rsc = '12:I["IntlProviderClient",{"messages":{"2605000_01":"蒼炎刃鬼ex掉落活動","110":"擲泥"}}]'

    messages = rx_events.extract_messages_from_rsc(rsc)

    assert messages["2605000_01"] == "蒼炎刃鬼ex掉落活動"
    assert messages["110"] == "擲泥"


def test_resolve_event_name_prefers_event_specific_namespace() -> None:
    messages = rx_events.extract_messages_from_rsc(
        '5:["$",{"messages":{"Game":{"Master":{"Battle":{"PvpEmblem":{"14":"進擊悖謬 勳章活動"},'
        '"SoloEvent":{"2605000_01":"蒼炎刃鬼ex掉落活動"}}}},"Other":{"14":"撞擊"}}}]'
    )

    assert rx_events.resolve_event_name("pvpEmblemBattle", "14", messages) == "進擊悖謬 勳章活動"
    assert rx_events.resolve_event_name("soloBattle", "2605000_01", messages) == "蒼炎刃鬼ex掉落活動"


def test_cli_list_outputs_paginated_json(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    monkeypatch.setattr(rx_events, "load_events", lambda: [_event(), _event(event_id="EV_EXPIRED", end=NOW - 1)])
    monkeypatch.setattr(rx_events, "load_i18n_messages", lambda: {"2605000_01": "蒼炎刃鬼ex掉落活動"})
    monkeypatch.setattr(rx_events.time, "time", lambda: NOW)

    code = rx_events.main(["list", "--state", "current", "--page", "1", "--limit", "20", "--json"])

    assert code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["source"] == "raenonx"
    assert payload["total"] == 1
    assert payload["items"][0]["name"] == "蒼炎刃鬼ex掉落活動"


def test_cli_rejects_invalid_limit(capsys: pytest.CaptureFixture[str]) -> None:
    code = rx_events.main(["list", "--limit", "101"])

    assert code == 2
    assert "limit" in capsys.readouterr().err


def test_cli_get_outputs_event_by_type_and_id(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    monkeypatch.setattr(
        rx_events,
        "load_events",
        lambda: [
            _event("wonderPickFree", "SC_GC_2605000_01"),
            _event("wonderPickChansey", "SC_GC_2605000_01"),
        ],
    )
    monkeypatch.setattr(rx_events, "load_i18n_messages", lambda: {})
    monkeypatch.setattr(rx_events.time, "time", lambda: NOW)

    code = rx_events.main(["get", "--type", "wonderPickChansey", "--id", "SC_GC_2605000_01", "--json"])

    assert code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["type"] == "wonderPickChansey"
