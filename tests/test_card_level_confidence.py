from __future__ import annotations

import sys
from pathlib import Path

src_dir = Path(__file__).parent.parent / "src"
sys.path.insert(0, str(src_dir))

from ptcgp_auto.debug_tools.non_interactive import (
    Match,
    _cluster_boxes_by_proximity,
    _filter_card_bboxes_by_area_ratio,
    _non_max_suppression_matches,
    _pick_best_scale_by_groups,
    _compute_card_roi,
    _parse_template_list,
)


def test_non_max_suppression_prefers_higher_confidence() -> None:
    matches = [
        Match(box=(0, 0, 10, 10), confidence=0.61),
        Match(box=(1, 1, 11, 11), confidence=0.92),
    ]

    kept = _non_max_suppression_matches(matches, overlap_thresh=0.5)

    assert len(kept) == 1
    assert kept[0].confidence == 0.92


def test_cluster_groups_preserve_confidence() -> None:
    matches = [
        Match(box=(0, 0, 10, 10), confidence=0.7),
        Match(box=(20, 1, 30, 11), confidence=0.8),
        Match(box=(200, 0, 210, 10), confidence=0.9),
    ]

    groups = _cluster_boxes_by_proximity(matches, gap_threshold=50, y_tolerance=20)

    assert [len(g) for g in groups] == [2, 1]
    assert [m.confidence for m in groups[0]] == [0.7, 0.8]


def test_pick_best_scale_prefers_larger_group() -> None:
    scale_to_groups = [
        (
            0.56,
            [
                [Match(box=(0, 0, 10, 10), confidence=0.90)],
            ],
        ),
        (
            0.57,
            [
                [
                    Match(box=(0, 0, 10, 10), confidence=0.65),
                    Match(box=(20, 0, 30, 10), confidence=0.63),
                    Match(box=(40, 0, 50, 10), confidence=0.64),
                    Match(box=(60, 0, 70, 10), confidence=0.62),
                ],
            ],
        ),
    ]

    best_scale = _pick_best_scale_by_groups(scale_to_groups)
    assert best_scale == 0.57


def test_parse_template_list() -> None:
    assert _parse_template_list("a,b,c") == ["a", "b", "c"]
    assert _parse_template_list("a") == ["a"]


def test_compute_card_roi_uses_ratios() -> None:
    card = (100, 200, 100 + 901, 200 + 1256)
    roi = _compute_card_roi(card)
    assert roi[0] == 100
    assert roi[3] == 200 + 1256
    assert roi[2] - roi[0] == int(901 * (248 / 901))
    assert roi[3] - roi[1] == int(1256 * (203 / 1256))


def test_filter_card_bboxes_by_area_ratio() -> None:
    b1 = (0, 0, 100, 200)
    b2 = (0, 0, 50, 80)
    area_by_bbox = {
        b1: 0.30,
        b2: 0.05,
    }

    kept = _filter_card_bboxes_by_area_ratio(
        [b1, b2], area_by_bbox, min_ratio_of_max=0.4
    )

    assert kept == [b1]
