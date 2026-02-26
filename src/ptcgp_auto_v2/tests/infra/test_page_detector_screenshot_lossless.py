# -*- coding: utf-8 -*-
"""PageDetector 截图参数透传测试。"""

from types import SimpleNamespace

from PIL import Image

from ptcgp_auto_v2.infra.page_detector import PageDetector


class _FakeAdb:
    """记录截图调用参数。"""

    def __init__(self):
        self.lossless_calls = []
        self.image = Image.new("RGB", (10, 10), (0, 0, 0))

    def screenshot(self, lossless: bool = False):
        self.lossless_calls.append(lossless)
        return self.image


class _FakeOcr:
    """最小 OCR 桩。"""

    def recognize_as_dict(self, screenshot):
        return [{"text": "foo", "box": (0, 0, 2, 2)}]

    def match_text(self, target, text, exact_match=False):
        if exact_match:
            return target == text
        return target in text

    def find_text(self, screenshot, text, exact_match=False):
        return SimpleNamespace(box=(1, 2, 3, 4))


class _FakeTemplate:
    """最小模板桩。"""

    def find_box(self, screenshot, template_name, threshold):
        return (2, 3, 4, 5)

    def find_all(self, screenshot, template_name, threshold, scale=1.0):
        return []

    def find_with_scale(self, screenshot, template_name, scale=1.0, threshold=None):
        return None


def _build_detector() -> tuple[PageDetector, _FakeAdb]:
    adb = _FakeAdb()
    detector = PageDetector(
        adb=adb,
        ocr_engine=_FakeOcr(),
        template_matcher=_FakeTemplate(),
    )
    return detector, adb


def test_detect_forwards_lossless():
    """detect 应透传 lossless 参数。"""
    detector, adb = _build_detector()
    detector.load_task_pages([{"name": "p1", "identifiers": ["foo"], "priority": 1}])

    detector.detect(lossless=True)

    assert adb.lossless_calls == [True]


def test_capture_forwards_lossless():
    """capture 应透传 lossless 参数。"""
    detector, adb = _build_detector()

    detector.capture(lossless=True)

    assert adb.lossless_calls == [True]


def test_find_text_forwards_lossless():
    """find_text 应透传 lossless 参数。"""
    detector, adb = _build_detector()

    detector.find_text("foo", lossless=True)

    assert adb.lossless_calls == [True]


def test_find_template_forwards_lossless_when_no_cache():
    """find_template 在无缓存时应透传 lossless 参数。"""
    detector, adb = _build_detector()

    detector.find_template("icon_x", lossless=True)

    assert adb.lossless_calls == [True]
