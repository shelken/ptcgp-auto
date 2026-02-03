# -*- coding: utf-8 -*-

from ptcgp_auto_v2.infra.icon_group_detector import IconHit, IconGroupDetector


def test_group_icons_by_row_and_gap():
    hits = [
        IconHit("diamond", 0.9, (0, 0, 10, 10), (5, 5)),
        IconHit("diamond", 0.9, (20, 0, 30, 10), (25, 5)),
        IconHit("diamond", 0.9, (60, 0, 70, 10), (65, 5)),
    ]

    detector = IconGroupDetector()
    groups = detector.group_hits(hits, row_tol=6, gap=25, min_count=1)

    counts = [group.count for group in groups]
    assert counts == [2, 1]
