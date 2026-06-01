#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""查询 RaenonX PTCGP 活动数据。"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime
from typing import Any

SOURCE_URL = "https://ptcgp.raenonx.cc/zh/event"
EVENT_BRIEF_URL = "https://ptcgp.raenonx.cc/api/data/event-brief"
UPCOMING_SECONDS = 30 * 24 * 60 * 60
MAX_LIMIT = 100
HTTP_TIMEOUT = 20
CARD_ID_RE = re.compile(r"^(?:PK|TR)_")
DPL_RE = re.compile(r"[?&]dpl=([^\"'&<>\\]+)")
MESSAGE_PAIR_RE = re.compile(r'"([^"\\]*(?:\\.[^"\\]*)*)":"([^"\\]*(?:\\.[^"\\]*)*)"')


def fetch_text(url: str, accept: str = "*/*", extra_headers: dict[str, str] | None = None) -> str:
    headers = {
        "Accept": accept,
        "User-Agent": "ptcgp-auto/ptcgp-knowledge (+https://github.com/shelken/ptcgp-auto)",
    }
    if extra_headers:
        headers.update(extra_headers)
    request = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(request, timeout=HTTP_TIMEOUT) as response:
            if response.status != 200:
                raise RuntimeError(f"HTTP {response.status}: {url}")
            return response.read().decode("utf-8")
    except urllib.error.URLError as exc:
        raise RuntimeError(f"请求失败: {url}: {exc}") from exc


def load_events() -> list[dict[str, Any]]:
    text = fetch_text(EVENT_BRIEF_URL, "application/json")
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise RuntimeError("RaenonX event-brief 返回内容不是 JSON") from exc
    if not isinstance(data, list):
        raise RuntimeError("RaenonX event-brief 顶层不是 list")
    return data


def extract_dpl(html: str) -> str | None:
    match = DPL_RE.search(html)
    return match.group(1) if match else None


def load_i18n_messages() -> dict[str, str]:
    html = fetch_text(SOURCE_URL, "text/html")
    dpl = extract_dpl(html)
    if not dpl:
        raise RuntimeError("无法从 RaenonX 活动页提取 dpl")
    rsc_url = f"{SOURCE_URL}?_rsc=1&dpl={dpl}"
    rsc = fetch_text(rsc_url, "text/x-component", {"RSC": "1"})
    return extract_messages_from_rsc(rsc)


def flatten_messages(value: Any, prefix: str = "") -> dict[str, str]:
    messages: dict[str, str] = {}
    if isinstance(value, dict):
        for key, nested in value.items():
            path = f"{prefix}.{key}" if prefix else str(key)
            if isinstance(nested, str):
                messages[path] = nested
                messages.setdefault(str(key), nested)
            else:
                messages.update(flatten_messages(nested, path))
    return messages


def extract_messages_from_rsc(rsc: str) -> dict[str, str]:
    marker = '"messages":'
    start = rsc.find(marker)
    if start >= 0:
        decoder = json.JSONDecoder()
        try:
            value, _ = decoder.raw_decode(rsc[start + len(marker) :])
            return flatten_messages(value)
        except json.JSONDecodeError:
            pass
    messages: dict[str, str] = {}
    for key_raw, value_raw in MESSAGE_PAIR_RE.findall(rsc):
        try:
            key = json.loads(f'"{key_raw}"')
            value = json.loads(f'"{value_raw}"')
        except json.JSONDecodeError:
            continue
        if isinstance(key, str) and isinstance(value, str):
            messages.setdefault(key, value)
    return messages


def resolve_event_name(event_type: str, name_i18n_id: Any, messages: dict[str, str]) -> str | None:
    if name_i18n_id is None:
        return None
    key = str(name_i18n_id)
    scoped_prefixes = {
        "soloBattle": ["Game.Master.Battle.SoloEvent"],
        "pvpEmblemBattle": ["Game.Master.Battle.PvpEmblem"],
        "missionGroup": ["Game.Master.Mission.Group"],
    }.get(event_type, [])
    for prefix in scoped_prefixes:
        value = messages.get(f"{prefix}.{key}")
        if value:
            return value
    return messages.get(key)


def classify_state(start_epoch: int | None, end_epoch: int | None, now_epoch: int | None = None) -> str:
    now = int(time.time()) if now_epoch is None else int(now_epoch)
    start = int(start_epoch or 0)
    end = int(end_epoch or 0)
    if end <= 0:
        return "permanent"
    if start <= now < end:
        return "current"
    if end <= now:
        return "expired"
    if start <= now + UPCOMING_SECONDS:
        return "upcoming"
    return "future"


def validate_pagination(page: int, limit: int) -> None:
    if page < 1:
        raise ValueError("page 必须大于等于 1")
    if limit < 1 or limit > MAX_LIMIT:
        raise ValueError(f"limit 必须在 1 到 {MAX_LIMIT} 之间")


def local_time(epoch: int | None) -> str | None:
    if not epoch:
        return None
    return datetime.fromtimestamp(int(epoch)).strftime("%Y-%m-%d %H:%M:%S")


def iter_values(value: Any) -> Any:
    if isinstance(value, dict):
        for nested in value.values():
            yield nested
            yield from iter_values(nested)
    elif isinstance(value, list):
        for item in value:
            yield item
            yield from iter_values(item)


def reward_from_container(container: Any) -> dict[str, Any] | None:
    if not isinstance(container, dict):
        return None
    meta = container.get("meta")
    if not isinstance(meta, dict):
        return None
    reward_id = meta.get("id")
    reward_type = meta.get("type")
    if not reward_id and not reward_type:
        return None
    return {"type": reward_type, "id": reward_id, "count": container.get("count", 1)}


def summarize_rewards(data: dict[str, Any]) -> tuple[list[dict[str, Any]], list[str]]:
    rewards: list[dict[str, Any]] = []
    seen: set[tuple[Any, Any, Any]] = set()
    for value in iter_values(data):
        reward = reward_from_container(value)
        if not reward:
            continue
        key = (reward.get("type"), reward.get("id"), reward.get("count"))
        if key in seen:
            continue
        seen.add(key)
        rewards.append(reward)
    return rewards, []


def extract_related_card_ids(data: dict[str, Any], rewards: list[dict[str, Any]]) -> list[str]:
    ids: set[str] = set()
    for reward in rewards:
        reward_id = reward.get("id")
        if isinstance(reward_id, str) and CARD_ID_RE.match(reward_id):
            ids.add(reward_id)
    for value in iter_values(data):
        if isinstance(value, str) and CARD_ID_RE.match(value):
            ids.add(value)
    return sorted(ids)


def normalize_event(item: dict[str, Any], messages: dict[str, str], now_epoch: int | None = None) -> dict[str, Any]:
    event_type = str(item.get("type") or "unknown")
    data = item.get("data")
    if not isinstance(data, dict):
        data = {}
    event_id = str(data.get("id") or item.get("id") or "")
    timeframe = data.get("timeframe") if isinstance(data.get("timeframe"), dict) else {}
    start_epoch = int(timeframe.get("startEpoch") or 0)
    end_epoch = int(timeframe.get("endEpoch") or 0)
    name_i18n_id = data.get("nameI18nId")
    name = resolve_event_name(event_type, name_i18n_id, messages)
    warnings: list[str] = []
    title_fallback = name or event_id or str(data.get("meta", {}).get("seasonId") or "unknown")
    if name_i18n_id is None:
        warnings.append("missing nameI18nId")
    elif name is None:
        warnings.append(f"missing i18n message: {name_i18n_id}")
    rewards, reward_warnings = summarize_rewards(data)
    warnings.extend(reward_warnings)
    return {
        "type": event_type,
        "id": event_id,
        "name": name,
        "nameI18nId": name_i18n_id,
        "titleFallback": title_fallback,
        "state": classify_state(start_epoch, end_epoch, now_epoch),
        "startEpoch": start_epoch or None,
        "endEpoch": end_epoch or None,
        "startLocal": local_time(start_epoch),
        "endLocal": local_time(end_epoch),
        "rewardSummary": rewards,
        "relatedCardIds": extract_related_card_ids(data, rewards),
        "sourceUrl": SOURCE_URL,
        "warnings": warnings,
    }


def find_event(events: list[dict[str, Any]], event_type: str, event_id: str) -> dict[str, Any]:
    for event in events:
        if event.get("type") == event_type and event.get("id") == event_id:
            return event
    raise LookupError(f"找不到活动: type={event_type}, id={event_id}")


def paginate(events: list[dict[str, Any]], page: int, limit: int) -> dict[str, Any]:
    validate_pagination(page, limit)
    start = (page - 1) * limit
    end = start + limit
    return {"source": "raenonx", "sourceUrl": SOURCE_URL, "page": page, "limit": limit, "total": len(events), "items": events[start:end]}


def sort_events(events: list[dict[str, Any]], sort_key: str) -> list[dict[str, Any]]:
    field, descending = {
        "start-desc": ("startEpoch", True),
        "start-asc": ("startEpoch", False),
        "end-desc": ("endEpoch", True),
        "end-asc": ("endEpoch", False),
    }[sort_key]
    return sorted(events, key=lambda event: event.get(field) or 0, reverse=descending)


def load_normalized_events() -> tuple[list[dict[str, Any]], list[str]]:
    warnings: list[str] = []
    try:
        messages = load_i18n_messages()
    except RuntimeError as exc:
        messages = {}
        warnings.append(str(exc))
    now = int(time.time())
    return [normalize_event(item, messages, now) for item in load_events()], warnings


def print_json(payload: Any) -> None:
    print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))


def print_text(events: list[dict[str, Any]], warnings: list[str] | None = None) -> None:
    for warning in warnings or []:
        print(f"WARNING: {warning}", file=sys.stderr)
    for event in events:
        print(f"[{event['state']}] {event['titleFallback']}")
        print(f"type: {event['type']}")
        print(f"id: {event['id']}")
        print(f"time: {event['startLocal']} ~ {event['endLocal']}")
        rewards = event.get("rewardSummary") or []
        reward_text = ", ".join(f"{item.get('type')} {item.get('id')} x{item.get('count')}" for item in rewards) if rewards else "-"
        print(f"rewards: {reward_text}")
        related = event.get("relatedCardIds") or []
        if related:
            print(f"related cards: {', '.join(related)}")
        if event.get("warnings"):
            print(f"warnings: {'; '.join(event['warnings'])}")
        print(f"source: {event['sourceUrl']}")
        print()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="查询 RaenonX PTCGP 活动数据")
    subparsers = parser.add_subparsers(dest="command", required=True)

    list_parser = subparsers.add_parser("list", help="分页列出活动")
    list_parser.add_argument("--state", choices=["current", "upcoming", "future", "expired", "permanent"])
    list_parser.add_argument("--type")
    list_parser.add_argument("--page", type=int, default=1)
    list_parser.add_argument("--limit", type=int, default=20)
    list_parser.add_argument("--sort", choices=["start-desc", "start-asc", "end-desc", "end-asc"], default="start-desc")
    list_parser.add_argument("--json", action="store_true")

    get_parser = subparsers.add_parser("get", help="按 type/id 查询单个活动")
    get_parser.add_argument("--type", required=True)
    get_parser.add_argument("--id", required=True)
    get_parser.add_argument("--json", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    try:
        args = parser.parse_args(argv)
        if args.command == "list":
            validate_pagination(args.page, args.limit)
        events, warnings = load_normalized_events()
        if args.command == "list":
            if args.state:
                events = [event for event in events if event["state"] == args.state]
            if args.type:
                events = [event for event in events if event["type"] == args.type]
            events = sort_events(events, args.sort)
            payload = paginate(events, args.page, args.limit)
            if warnings:
                payload["warnings"] = warnings
            if args.json:
                print_json(payload)
            else:
                print_text(payload["items"], warnings)
            return 0
        event = find_event(events, args.type, args.id)
        if warnings:
            event = {**event, "warnings": [*event.get("warnings", []), *warnings]}
        if args.json:
            print_json(event)
        else:
            print_text([event])
        return 0
    except (LookupError, RuntimeError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
