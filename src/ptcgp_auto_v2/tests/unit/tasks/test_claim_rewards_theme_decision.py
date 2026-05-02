# -*- coding: utf-8 -*-
"""任务奖励页主题收藏决策测试。"""

from ptcgp_auto_v2.tasks.claim_rewards import ClaimRewardsTask


def _ocr(text: str) -> dict:
    return {"text": text, "box": (10, 10, 100, 40)}


def _task(claim_all_clickable: bool) -> ClaimRewardsTask:
    task = ClaimRewardsTask.__new__(ClaimRewardsTask)
    task._is_claim_all_clickable = lambda box, screenshot: claim_all_clickable
    return task


def test_green_claim_all_skips_theme_collection():
    """全部领取为绿色时，当前 Tab 自己处理，不进入主题收藏。"""
    task = _task(claim_all_clickable=True)

    assert not task._needs_theme_collection([_ocr("全部領取")], object())


def test_gray_claim_all_checks_theme_collection():
    """全部领取置灰时，需要进入主题收藏。"""
    task = _task(claim_all_clickable=False)

    assert task._needs_theme_collection([_ocr("全部領取")], object())


def test_exact_claim_button_skips_theme_collection():
    """精确出现领取时，当前 Tab 自己处理，不进入主题收藏。"""
    task = _task(claim_all_clickable=False)

    assert not task._needs_theme_collection([_ocr("領取")], object())


def test_no_claim_entry_checks_theme_collection():
    """没有全部领取也没有领取时，需要进入主题收藏。"""
    task = _task(claim_all_clickable=False)

    assert task._needs_theme_collection([_ocr("每日任務")], object())
