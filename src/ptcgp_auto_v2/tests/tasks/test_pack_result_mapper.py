# -*- coding: utf-8 -*-
"""开包结果映射与归并测试。"""

from ptcgp_auto_v2.tasks.utils.pack_result_rows import (
    BASE_COMMON_CARD_X_TOLERANCE,
    build_pack_groups,
    build_row_signature,
    group_rows,
    is_same_row,
    merge_or_append_rows,
)


def make_card(
    card_id: int,
    x: float,
    y: float,
    confidence: float = 0.9,
) -> dict:
    """构造测试卡牌。"""
    return {
        "card_id": card_id,
        "set_code": "A1",
        "card_number": card_id,
        "center_x": x,
        "center_y": y,
        "confidence": confidence,
        "position": 1,
    }


def test_group_rows_should_split_by_center_y() -> None:
    cards = [
        make_card(3, 520, 105),
        make_card(1, 120, 100),
        make_card(2, 320, 98),
        make_card(4, 180, 210),
        make_card(5, 380, 215),
    ]

    rows = group_rows(cards, row_threshold=30)

    assert len(rows) == 2
    assert build_row_signature(rows[0]) == ["id:1", "id:2", "id:3"]
    assert build_row_signature(rows[1]) == ["id:4", "id:5"]


def test_is_same_row_should_accept_ordered_subset() -> None:
    existing = [make_card(1, 120, 100), make_card(2, 320, 100), make_card(3, 520, 100)]
    incoming = [make_card(2, 318, 105), make_card(3, 518, 105)]

    assert (
        is_same_row(existing, incoming, x_tolerance=BASE_COMMON_CARD_X_TOLERANCE)
        is True
    )


def test_is_same_row_should_reject_single_card_overlap() -> None:
    existing = [make_card(1, 248, 100), make_card(2, 472, 100)]
    incoming = [make_card(2, 360, 102), make_card(3, 576, 102), make_card(4, 142, 102)]

    assert (
        is_same_row(existing, incoming, x_tolerance=BASE_COMMON_CARD_X_TOLERANCE)
        is False
    )


def test_merge_or_append_rows_should_replace_with_more_complete_row() -> None:
    logical_rows = [[make_card(2, 320, 100), make_card(3, 520, 100)]]
    incoming_rows = [
        [make_card(1, 120, 102), make_card(2, 322, 102), make_card(3, 522, 102)]
    ]

    stats = merge_or_append_rows(
        logical_rows,
        incoming_rows,
        x_tolerance=BASE_COMMON_CARD_X_TOLERANCE,
    )

    assert stats["appended"] == 0
    assert stats["replaced"] == 1
    assert stats["skipped"] == 0
    assert build_row_signature(logical_rows[0]) == ["id:1", "id:2", "id:3"]


def test_merge_or_append_rows_should_merge_partial_overlap_row() -> None:
    logical_rows = [[make_card(2, 320, 100), make_card(3, 520, 100)]]
    incoming_rows = [
        [make_card(1, 120, 102), make_card(2, 322, 102, 0.95), make_card(3, 522, 102)]
    ]

    stats = merge_or_append_rows(
        logical_rows,
        incoming_rows,
        x_tolerance=BASE_COMMON_CARD_X_TOLERANCE,
    )

    assert stats["appended"] == 0
    assert stats["replaced"] == 1
    assert stats["skipped"] == 0
    assert build_row_signature(logical_rows[0]) == ["id:1", "id:2", "id:3"]


def test_merge_or_append_rows_should_keep_single_card_fragment() -> None:
    logical_rows: list[list[dict]] = []
    incoming_rows = [[make_card(1, 120, 100)]]

    stats = merge_or_append_rows(
        logical_rows,
        incoming_rows,
        x_tolerance=BASE_COMMON_CARD_X_TOLERANCE,
    )

    assert stats["appended"] == 1
    assert stats["replaced"] == 0
    assert stats["skipped"] == 0
    assert build_row_signature(logical_rows[0]) == ["id:1"]


def test_merge_or_append_rows_should_not_merge_one_card_overlap_row() -> None:
    logical_rows = [[make_card(10, 248, 100), make_card(11, 472, 100)]]
    incoming_rows = [
        [make_card(11, 360, 102), make_card(12, 576, 102), make_card(13, 142, 102)]
    ]

    stats = merge_or_append_rows(
        logical_rows,
        incoming_rows,
        x_tolerance=BASE_COMMON_CARD_X_TOLERANCE,
    )

    assert stats["appended"] == 1
    assert stats["replaced"] == 0
    assert stats["skipped"] == 0
    assert len(logical_rows) == 2
    assert build_row_signature(logical_rows[0]) == ["id:10", "id:11"]
    assert build_row_signature(logical_rows[1]) == ["id:13", "id:11", "id:12"]


def test_merge_or_append_rows_should_match_overlap_row_after_two_new_rows() -> None:
    logical_rows = [
        [make_card(1, 120, 100), make_card(2, 320, 100)],
        [make_card(3, 120, 200), make_card(4, 320, 200)],
        [make_card(5, 120, 300), make_card(6, 320, 300)],
    ]
    first_screen_rows = [
        [make_card(7, 120, 400), make_card(8, 320, 400)],
        [make_card(9, 120, 500), make_card(10, 320, 500)],
    ]
    second_screen_rows = [
        [make_card(5, 122, 600), make_card(6, 322, 600)],
    ]

    first_stats = merge_or_append_rows(
        logical_rows,
        first_screen_rows,
        x_tolerance=BASE_COMMON_CARD_X_TOLERANCE,
    )
    second_stats = merge_or_append_rows(
        logical_rows,
        second_screen_rows,
        x_tolerance=BASE_COMMON_CARD_X_TOLERANCE,
    )

    assert first_stats["appended"] == 2
    assert second_stats["appended"] == 0
    assert second_stats["skipped"] == 1
    assert len(logical_rows) == 5
    assert build_row_signature(logical_rows[-1]) == ["id:9", "id:10"]


def test_is_same_row_should_reject_same_length_single_card_overlap() -> None:
    existing = [make_card(1, 248, 100), make_card(2, 472, 100)]
    incoming = [make_card(3, 248, 102), make_card(2, 472, 102)]

    assert (
        is_same_row(existing, incoming, x_tolerance=BASE_COMMON_CARD_X_TOLERANCE)
        is False
    )


def test_build_pack_groups_should_reindex_positions_per_pack() -> None:
    rows = [
        [make_card(1, 120, 100), make_card(2, 320, 100), make_card(3, 520, 100)],
        [make_card(4, 180, 210), make_card(5, 380, 210)],
        [make_card(6, 120, 320), make_card(7, 320, 320), make_card(8, 520, 320)],
        [make_card(9, 180, 430), make_card(10, 380, 430)],
    ]

    groups = build_pack_groups(rows, rows_per_pack=2)

    assert len(groups) == 2
    assert [card["position"] for card in groups[0]] == [1, 2, 3, 4, 5]
    assert [card["position"] for card in groups[1]] == [1, 2, 3, 4, 5]
