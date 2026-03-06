# -*- coding: utf-8 -*-
"""OCR 引擎异常降级测试。"""

import sys
import types
from contextlib import nullcontext

from PIL import Image

from ptcgp_auto_v2.infra.ocr import OcrEngine


def test_recognize_returns_empty_list_when_quartz_symbol_missing(monkeypatch):
    """Quartz 图片解码符号缺失时，OCR 应降级为空结果而不是抛异常。"""
    monkeypatch.setattr("platform.system", lambda: "Darwin")

    fake_vision = types.ModuleType("Vision")
    fake_quartz = types.ModuleType("Quartz")

    def _missing_symbol(name: str):
        if name == "CGImageSourceCreateWithData":
            raise KeyError(name)
        raise AttributeError(name)

    fake_quartz.__getattr__ = _missing_symbol

    fake_foundation = types.ModuleType("Foundation")

    class FakeNSData:
        """最小 NSData 替身。"""

        @staticmethod
        def dataWithBytes_length_(_data, _length):
            return object()

    fake_foundation.NSData = FakeNSData

    fake_objc = types.ModuleType("objc")
    fake_objc.autorelease_pool = nullcontext

    monkeypatch.setitem(sys.modules, "Vision", fake_vision)
    monkeypatch.setitem(sys.modules, "Quartz", fake_quartz)
    monkeypatch.setitem(sys.modules, "Foundation", fake_foundation)
    monkeypatch.setitem(sys.modules, "objc", fake_objc)

    engine = OcrEngine()

    assert engine.recognize(Image.new("RGB", (16, 16), "white")) == []
