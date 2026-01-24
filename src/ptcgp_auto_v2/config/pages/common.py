# -*- coding: utf-8 -*-
"""
公共页面规则
"""

from ptcgp_auto_v2.locales.zh_Hant import TEXT_PATTERNS


def _get_patterns(text_patterns: dict, key: str) -> list[str]:
    patterns = text_patterns.get(key, [])
    return patterns if isinstance(patterns, list) else []


COMMON_PAGES = [
    {
        "name": "popup_ok",
        "identifiers": _get_patterns(TEXT_PATTERNS, "popup_ok"),
        "priority": 150,
        "exact_match": True,
    },
    {
        "name": "network_error_popup",
        "identifiers": _get_patterns(TEXT_PATTERNS, "network_error_popup"),
        "priority": 150,
        "exact_match": True,
    },
    {
        "name": "continue_button",
        "identifiers": _get_patterns(TEXT_PATTERNS, "continue_button"),
        "priority": 150,
        "exact_match": True,
    },
    {
        "name": "tap_to_continue",
        "identifiers": _get_patterns(TEXT_PATTERNS, "tap_to_continue"),
        "priority": 150,
    },
    {
        "name": "game_open_page",
        "identifiers": _get_patterns(TEXT_PATTERNS, "game_open_page"),
        "priority": 150,
    },
    {
        # 游戏内通用关闭按钮（模板匹配）
        "name": "btn_close",
        "templates": ["btn_close"],
        "priority": 500,
    },
    {
        "name": "_close_app_popup",
        "identifiers": _get_patterns(TEXT_PATTERNS, "close_app_popup"),
        "match_all": True,
        "priority": 900,
    },
    {
        "name": "_main_page",
        "identifiers": _get_patterns(TEXT_PATTERNS, "main_page"),
        "match_all": True,
        "exclude_identifiers": _get_patterns(TEXT_PATTERNS, "close_app_popup"),
        "priority": 920,
    },
    {
        "name": "_auth_again",
        "identifiers": _get_patterns(TEXT_PATTERNS, "auth_again"),
        "priority": 920,
    },
]

__all__ = ["COMMON_PAGES"]
