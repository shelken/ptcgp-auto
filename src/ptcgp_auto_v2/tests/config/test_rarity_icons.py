# -*- coding: utf-8 -*-
"""稀有度映射配置测试。"""

from ptcgp_auto_v2.config.rarity_icons import get_rarity_display


def test_get_rarity_display_returns_zh_label_for_known_code():
    """已知稀有度应返回中文展示文案。"""
    assert get_rarity_display("RR", "zh_CN") == "RR (4钻)"


def test_get_rarity_display_returns_en_label_for_non_zh():
    """非中文语言应返回英文展示文案。"""
    assert get_rarity_display("UR", "en") == "UR (Crown)"


def test_get_rarity_display_fallbacks_to_code_for_unknown():
    """未知稀有度应回退原始代码。"""
    assert get_rarity_display("UNKNOWN", "zh_CN") == "UNKNOWN"
