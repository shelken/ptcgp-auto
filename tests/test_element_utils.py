# -*- coding: utf-8 -*-

from ptcgp_auto_v2.web.utils.element_utils import normalize_elements


def test_normalize_elements_dedup_and_lowercase():
    elements = ["Fire", "fire", "WATER", "water", None, ""]
    assert normalize_elements(elements) == ["fire", "water"]
