# -*- coding: utf-8 -*-
"""开包结果页逻辑行归并与分组工具。"""

from __future__ import annotations


# 重叠卡横向槽位容忍值（基于 1080 宽度基准像素）。
# 运行态必须经 adb.scaled_x() 缩放后使用，禁止直接拿基准值参与判断。
BASE_COMMON_CARD_X_TOLERANCE = 60


def _build_card_key(card: dict) -> str | None:
    """构建单张卡的稳定键，优先使用 card_id。"""
    card_id = card.get("card_id")
    if card_id is not None:
        return f"id:{card_id}"

    set_code = card.get("set_code")
    card_number = card.get("card_number")
    if set_code and card_number is not None:
        return f"{set_code}:{card_number}"

    return None


def build_row_signature(row: list[dict]) -> list[str]:
    """按从左到右构建一行的稳定签名。"""
    ordered = sorted(row, key=lambda item: float(item.get("center_x") or 0.0))
    signature: list[str] = []
    for card in ordered:
        card_key = _build_card_key(card)
        if card_key:
            signature.append(card_key)
    return signature


def _is_ordered_subsequence(shorter: list[str], longer: list[str]) -> bool:
    """判断 shorter 是否为 longer 的有序子序列。"""
    if not shorter:
        return False

    index = 0
    for item in longer:
        if item == shorter[index]:
            index += 1
            if index == len(shorter):
                return True
    return False


def _has_aligned_common_card_x(
    existing_row: list[dict],
    incoming_row: list[dict],
    common: list[str],
    x_tolerance: float,
) -> bool:
    """判断所有重叠卡是否都落在接近的 x 槽位上。"""
    if not common:
        return False

    for card_key in common:
        existing_x_values = [
            float(card.get("center_x") or 0.0)
            for card in existing_row
            if _build_card_key(card) == card_key
        ]
        incoming_x_values = [
            float(card.get("center_x") or 0.0)
            for card in incoming_row
            if _build_card_key(card) == card_key
        ]
        for existing_x in existing_x_values:
            for incoming_x in incoming_x_values:
                if abs(existing_x - incoming_x) <= x_tolerance:
                    break
            else:
                continue
            break
        else:
            return False
    return True


def is_same_row(
    existing_row: list[dict],
    incoming_row: list[dict],
    x_tolerance: float,
) -> bool:
    """判断两行是否属于同一逻辑行。"""
    existing = build_row_signature(existing_row)
    incoming = build_row_signature(incoming_row)

    if not existing or not incoming:
        return False

    if existing == incoming:
        return True

    common = [item for item in existing if item in incoming]

    if _is_ordered_subsequence(incoming, existing) or _is_ordered_subsequence(
        existing, incoming
    ):
        return _has_aligned_common_card_x(
            existing_row, incoming_row, common, x_tolerance
        )

    # 10 包结果页允许 2 卡或 3 卡一行；只有 1 张重叠时，仅允许不同长度行做边缘补全。
    # 同长度行只重叠 1 张，实际日志里已证明会把相邻两行错并。
    if len(common) == 1:
        if len(existing) == len(incoming):
            return False
        return _has_aligned_common_card_x(
            existing_row, incoming_row, common, x_tolerance
        )

    if len(common) < 2:
        return False

    overlap_ratio = len(common) / min(len(existing), len(incoming))
    if overlap_ratio < 0.66:
        return False

    return (
        _is_ordered_subsequence(common, existing)
        and _is_ordered_subsequence(common, incoming)
        and _has_aligned_common_card_x(existing_row, incoming_row, common, x_tolerance)
    )


def merge_or_append_rows(
    logical_rows: list[list[dict]],
    incoming_rows: list[list[dict]],
    x_tolerance: float,
    tail_size: int = 3,
) -> dict[str, int]:
    """将新扫描行归并到逻辑行列表中。"""
    stats = {"appended": 0, "replaced": 0, "skipped": 0, "decisions": []}
    original_rows = list(logical_rows)
    matched_indices: list[int | None] = []

    for incoming_row in incoming_rows:
        matched_index: int | None = None
        start_index = max(0, len(original_rows) - tail_size)
        for index in range(len(original_rows) - 1, start_index - 1, -1):
            if is_same_row(original_rows[index], incoming_row, x_tolerance=x_tolerance):
                matched_index = index
                break
        matched_indices.append(matched_index)

    for row_index, incoming_row in enumerate(incoming_rows):
        incoming_signature = build_row_signature(incoming_row)
        if not incoming_signature:
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

        matched_index = matched_indices[row_index]

        if matched_index is None:
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

        previous_row = logical_rows[matched_index]
        previous_signature = build_row_signature(previous_row)

        if previous_signature == incoming_signature or _is_ordered_subsequence(
            incoming_signature, previous_signature
        ):
            stats["skipped"] += 1
            stats["decisions"].append(
                {
                    "action": "skip",
                    "incoming_row": incoming_row,
                    "matched_row": previous_row,
                    "result_row": previous_row,
                }
            )
            continue

        if _is_ordered_subsequence(previous_signature, incoming_signature):
            logical_rows[matched_index] = incoming_row
            stats["replaced"] += 1
            stats["decisions"].append(
                {
                    "action": "replace",
                    "incoming_row": incoming_row,
                    "matched_row": previous_row,
                    "result_row": incoming_row,
                }
            )
            continue

        stats["skipped"] += 1
        stats["decisions"].append(
            {
                "action": "skip",
                "incoming_row": incoming_row,
                "matched_row": previous_row,
                "result_row": previous_row,
            }
        )
        continue

    return stats


def has_incomplete_rows(rows: list[list[dict]]) -> bool:
    """判断当前逻辑行里是否还存在未补全的残行。"""
    return any(len(build_row_signature(row)) < 2 for row in rows)


def group_rows(cards: list[dict], row_threshold: int) -> list[list[dict]]:
    """按阅读顺序中的行信息分组。"""
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
        current_y = float(card.get("center_y") or 0.0)
        row_y = float(current_row[0].get("center_y") or 0.0)
        if abs(current_y - row_y) < row_threshold:
            current_row.append(card)
            continue

        current_row.sort(key=lambda item: float(item.get("center_x") or 0.0))
        rows.append(current_row)
        current_row = [card]

    current_row.sort(key=lambda item: float(item.get("center_x") or 0.0))
    rows.append(current_row)
    return rows


def build_pack_groups(
    rows: list[list[dict]], rows_per_pack: int = 2
) -> list[list[dict]]:
    """按固定行数将逻辑行切分为多包结果，并重建包内 position。"""
    if rows_per_pack <= 0 or len(rows) % rows_per_pack != 0:
        return []

    groups: list[list[dict]] = []
    for index in range(0, len(rows), rows_per_pack):
        pack_rows = rows[index : index + rows_per_pack]
        pack_cards: list[dict] = []
        for row in pack_rows:
            pack_cards.extend(row)

        normalized_cards: list[dict] = []
        for position, card in enumerate(pack_cards, start=1):
            normalized = dict(card)
            normalized["position"] = position
            normalized_cards.append(normalized)
        groups.append(normalized_cards)
    return groups
