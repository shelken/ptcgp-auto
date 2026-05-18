# -*- coding: utf-8 -*-
"""页面检测优先级测试。"""

from PIL import Image

from ptcgp_auto_v2.config.pages.common import COMMON_PAGES
from ptcgp_auto_v2.infra.adb import ScreenshotMode
from ptcgp_auto_v2.infra.page_detector import PageDetector
from ptcgp_auto_v2.tasks.claim_rewards import ClaimRewardsTask


class _Adb:
    def screenshot(self, **kwargs):
        return Image.new("RGB", (720, 1280), "black")

    def _resolve_screenshot_mode(self, ocr_mode, lossless):
        return ScreenshotMode.RPC_JPEG


class _OcrEngine:
    def __init__(self, texts: list[str]):
        self.texts = texts

    def recognize_as_dict(self, screenshot, **kwargs):
        return [
            {"text": text, "box": (10, 10 + index * 40, 200, 40 + index * 40)}
            for index, text in enumerate(self.texts)
        ]

    def match_text(self, identifier: str, ocr_text: str, exact_match: bool):
        if exact_match:
            return identifier == ocr_text
        return identifier in ocr_text


class _TemplateMatcher:
    def find(self, screenshot, template_name, threshold=None):
        return None


def test_android_anr_popup_has_priority_over_task_page():
    """Android 无响应弹窗必须优先于游戏任务页，避免被 rewards_page 抢匹配。"""
    detector = PageDetector(
        adb=_Adb(),
        ocr_engine=_OcrEngine(["每日", "Pocket没有响应", "× 关闭应用", "等待"]),
        template_matcher=_TemplateMatcher(),
        base_pages=COMMON_PAGES,
    )
    detector.load_task_pages(ClaimRewardsTask.pages)

    page_name, _ = detector.detect()

    assert page_name == "android_app_not_responding"
