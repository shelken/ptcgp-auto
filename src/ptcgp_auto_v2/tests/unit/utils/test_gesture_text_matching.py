# -*- coding: utf-8 -*-
"""手势 OCR 文本匹配语义测试。"""

from ptcgp_auto_v2.infra.ocr import match_ocr_text
from ptcgp_auto_v2.utils.gesture import find_text_matches, is_text_visible


def test_gesture_text_matching_uses_ocr_matcher_for_non_exact_cases():
    ocr_results = [
        {"text": "  Open Pack Hourglass  ", "box": (0, 0, 10, 10)},
        {"text": "Shop", "box": (10, 10, 20, 20)},
    ]
    patterns = ["pack hourglass"]

    assert match_ocr_text(patterns[0], ocr_results[0]["text"], exact_match=False)
    assert is_text_visible(ocr_results, patterns, exact=False)
    assert find_text_matches(ocr_results, patterns, exact=False) == [ocr_results[0]]


def test_gesture_text_matching_uses_ocr_matcher_for_exact_cases():
    ocr_results = [
        {"text": "Pack Hourglass", "box": (0, 0, 10, 10)},
        {"text": "PackHourglass", "box": (10, 10, 20, 20)},
    ]
    pattern = " pack hourglass "

    assert match_ocr_text(pattern, ocr_results[0]["text"], exact_match=True)
    assert not match_ocr_text(pattern, ocr_results[1]["text"], exact_match=True)
    assert is_text_visible(ocr_results, [pattern], exact=True)
    assert find_text_matches(ocr_results, [pattern], exact=True) == [ocr_results[0]]
