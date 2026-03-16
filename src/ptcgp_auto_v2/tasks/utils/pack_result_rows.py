# -*- coding: utf-8 -*-
"""开包结果页行归并工具。"""

from __future__ import annotations


def _card_key(card: dict) -> str | None:
    card_id = card.get("card_id")
    if card_id is not None:
        return f"id:{card_id}"
    set_code = card.get("set_code")
    card_number = card.get("card_number")
    if set_code and card_number is not None:
        return f"{set_code}:{card_number}"
    return None


def build_row_signature(row: list[dict]) -> list[str]:
    ordered = sorted(row, key=lambda item: float(item.get("center_x") or 0.0))
    return [key for card in ordered if (key := _card_key(card))]


def _median(values: list[float]) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    middle = len(ordered) // 2
    if len(ordered) % 2 == 1:
        return ordered[middle]
    return (ordered[middle - 1] + ordered[middle]) / 2.0


def _build_model(rows: list[list[dict]]) -> dict[str, dict[str, float]]:
    three_rows = [
        sorted(row, key=lambda item: float(item.get("center_x") or 0.0))
        for row in rows
        if len(row) == 3
    ]
    if three_rows:
        left = _median([float(row[0].get("center_x") or 0.0) for row in three_rows])
        middle = _median([float(row[1].get("center_x") or 0.0) for row in three_rows])
        right = _median([float(row[2].get("center_x") or 0.0) for row in three_rows])
    else:
        two_rows = [
            sorted(row, key=lambda item: float(item.get("center_x") or 0.0))
            for row in rows
            if len(row) == 2
        ]
        left_two = _median([float(row[0].get("center_x") or 0.0) for row in two_rows])
        right_two = _median([float(row[1].get("center_x") or 0.0) for row in two_rows])
        if left_two is None or right_two is None:
            return {}
        middle = (left_two + right_two) / 2.0
        left = 2 * left_two - middle
        right = 2 * right_two - middle
    if left is None or middle is None or right is None:
        return {}
    return {
        "three": {"left": left, "middle": middle, "right": right},
        "two": {
            "left": (left + middle) / 2.0,
            "right": (middle + right) / 2.0,
        },
    }


def _distance(
    xs: list[float], centers: dict[str, float], slots: tuple[str, ...]
) -> float:
    return sum(abs(x - centers[slot]) for x, slot in zip(xs, slots, strict=True))


def _classify_row(row: list[dict], rows_context: list[list[dict]]) -> dict | None:
    model = _build_model(rows_context)
    if not model:
        return None
    ordered = sorted(row, key=lambda item: float(item.get("center_x") or 0.0))
    xs = [float(card.get("center_x") or 0.0) for card in ordered]
    keys = [_card_key(card) for card in ordered]
    if not xs or any(key is None for key in keys):
        return None

    candidates: list[dict] = []
    if len(xs) == 3:
        candidates.append(
            {
                "layout": "three",
                "slots": ("left", "middle", "right"),
                "keys": tuple(keys),
                "complete": True,
                "distance": _distance(xs, model["three"], ("left", "middle", "right")),
            }
        )
    elif len(xs) == 2:
        candidates.append(
            {
                "layout": "two",
                "slots": ("left", "right"),
                "keys": tuple(keys),
                "complete": True,
                "distance": _distance(xs, model["two"], ("left", "right")),
            }
        )
        for slots in (("left", "middle"), ("left", "right"), ("middle", "right")):
            candidates.append(
                {
                    "layout": "three",
                    "slots": slots,
                    "keys": tuple(keys),
                    "complete": False,
                    "distance": _distance(xs, model["three"], slots),
                }
            )
    elif len(xs) == 1:
        for layout, slots in (
            ("two", (("left",), ("right",))),
            ("three", (("left",), ("middle",), ("right",))),
        ):
            for slot in slots:
                candidates.append(
                    {
                        "layout": layout,
                        "slots": slot,
                        "keys": tuple(keys),
                        "complete": False,
                        "distance": _distance(xs, model[layout], slot),
                    }
                )
    else:
        return None

    return min(
        candidates,
        key=lambda item: (
            item["distance"],
            0 if item["layout"] == "three" else 1,
            0 if not item["complete"] else 1,
        ),
    )


def build_row_slot_signature(row: list[dict]) -> tuple[str, ...]:
    classified = _classify_row(row, [row])
    if classified is None:
        return ()
    return tuple(
        f"{classified['layout']}:{slot}:{key}"
        for slot, key in zip(classified["slots"], classified["keys"], strict=True)
    )


def is_complete_row(row: list[dict]) -> bool:
    classified = _classify_row(row, [row])
    return bool(classified and classified["complete"])


def _same_row(
    existing_row: list[dict], incoming_row: list[dict], rows_context: list[list[dict]]
) -> bool:
    existing = _classify_row(existing_row, rows_context)
    incoming = _classify_row(incoming_row, rows_context)
    if existing is None or incoming is None or existing["layout"] != incoming["layout"]:
        return False
    existing_slots = dict(zip(existing["slots"], existing["keys"], strict=True))
    incoming_slots = dict(zip(incoming["slots"], incoming["keys"], strict=True))
    overlap = set(existing_slots) & set(incoming_slots)
    return bool(overlap) and all(
        existing_slots[slot] == incoming_slots[slot] for slot in overlap
    )


def is_same_row(existing_row: list[dict], incoming_row: list[dict]) -> bool:
    return _same_row(existing_row, incoming_row, [existing_row, incoming_row])


def _merge_row(
    existing_row: list[dict], incoming_row: list[dict], rows_context: list[list[dict]]
) -> list[dict]:
    existing = _classify_row(existing_row, rows_context)
    incoming = _classify_row(incoming_row, rows_context)
    if existing is None:
        return incoming_row
    if incoming is None:
        return existing_row
    return (
        incoming_row
        if len(incoming["slots"]) > len(existing["slots"])
        else existing_row
    )


def merge_or_append_rows(
    logical_rows: list[list[dict]], incoming_rows: list[list[dict]], tail_size: int = 3
) -> dict[str, object]:
    stats = {"appended": 0, "replaced": 0, "skipped": 0, "decisions": []}
    for incoming_row in incoming_rows:
        rows_context = logical_rows + incoming_rows
        incoming = _classify_row(incoming_row, rows_context)
        if incoming is None:
            stats["skipped"] += 1
            stats["decisions"].append(
                {
                    "action": "skip",
                    "incoming_row": incoming_row,
                    "matched_row": None,
                    "result_row": None,
                }
            )
            continue
        matched_indices = [
            index
            for index in range(
                len(logical_rows) - 1, max(-1, len(logical_rows) - tail_size - 1), -1
            )
            if _same_row(logical_rows[index], incoming_row, rows_context)
        ]
        if not matched_indices:
            logical_rows.append(incoming_row)
            stats["appended"] += 1
            stats["decisions"].append(
                {
                    "action": "append",
                    "incoming_row": incoming_row,
                    "matched_row": None,
                    "result_row": incoming_row,
                }
            )
            continue

        matched_indices.sort()
        base_index = matched_indices[-1]
        merged_row = incoming_row
        matched_rows = [logical_rows[index] for index in matched_indices]
        for matched_row in matched_rows:
            merged_row = _merge_row(matched_row, merged_row, rows_context)
        if build_row_signature(merged_row) == build_row_signature(
            logical_rows[base_index]
        ):
            stats["skipped"] += 1
            stats["decisions"].append(
                {
                    "action": "skip",
                    "incoming_row": incoming_row,
                    "matched_row": logical_rows[base_index],
                    "result_row": logical_rows[base_index],
                }
            )
            continue
        for index in reversed(matched_indices):
            if index != base_index:
                del logical_rows[index]
        logical_rows[base_index if base_index < len(logical_rows) else -1] = merged_row
        stats["replaced"] += 1
        stats["decisions"].append(
            {
                "action": "replace",
                "incoming_row": incoming_row,
                "matched_row": matched_rows[0],
                "result_row": merged_row,
            }
        )
    return stats


def has_incomplete_rows(rows: list[list[dict]]) -> bool:
    return any(len(build_row_signature(row)) < 2 for row in rows)


def get_missing_slots(row: list[dict], rows_context: list[list[dict]]) -> list[str]:
    classified = _classify_row(row, rows_context)
    if classified is None or classified["complete"]:
        return []
    expected_slots = (
        ["left", "right"]
        if classified["layout"] == "two"
        else ["left", "middle", "right"]
    )
    current_slots = set(classified["slots"])
    return [slot for slot in expected_slots if slot not in current_slots]


def group_rows(cards: list[dict], row_threshold: int) -> list[list[dict]]:
    if not cards:
        return []
    sorted_cards = sorted(
        cards,
        key=lambda item: (
            float(item.get("center_y") or 0.0),
            float(item.get("center_x") or 0.0),
        ),
    )
    rows: list[list[dict]] = []
    current_row = [sorted_cards[0]]
    for card in sorted_cards[1:]:
        if (
            abs(
                float(card.get("center_y") or 0.0)
                - float(current_row[0].get("center_y") or 0.0)
            )
            < row_threshold
        ):
            current_row.append(card)
            continue
        rows.append(
            sorted(current_row, key=lambda item: float(item.get("center_x") or 0.0))
        )
        current_row = [card]
    rows.append(
        sorted(current_row, key=lambda item: float(item.get("center_x") or 0.0))
    )
    return rows


def build_pack_groups(
    rows: list[list[dict]], rows_per_pack: int = 2
) -> list[list[dict]]:
    if rows_per_pack <= 0 or len(rows) % rows_per_pack != 0:
        return []
    groups: list[list[dict]] = []
    for index in range(0, len(rows), rows_per_pack):
        pack_cards: list[dict] = []
        for row in rows[index : index + rows_per_pack]:
            pack_cards.extend(row)
        groups.append(
            [
                {**card, "position": position}
                for position, card in enumerate(pack_cards, start=1)
            ]
        )
    return groups
