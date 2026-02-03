# -*- coding: utf-8 -*-
import pytest

from ptcgp_auto_v2.web.utils.form_utils import parse_optional_int


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (None, None),
        ("", None),
        (" ", None),
        ("12", 12),
        ("001", 1),
        ("abc", None),
    ],
)
def test_parse_optional_int(value, expected):
    assert parse_optional_int(value) == expected
