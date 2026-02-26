# -*- coding: utf-8 -*-
"""ADB 截图模式测试。"""

from typing import Any, cast

from PIL import Image

from ptcgp_auto_v2.infra.adb import AdbController


class _FakeDevice:
    """用于验证截图调用参数的假设备。"""

    def __init__(self):
        self.calls = []
        self.image = Image.new("RGB", (10, 10), (0, 0, 0))

    def screenshot(self, *args, **kwargs):
        self.calls.append((args, kwargs))
        return self.image


def test_screenshot_default_uses_u2_default_path():
    """默认 lossless=False 时应调用 u2 默认截图。"""
    adb = AdbController("127.0.0.1:5555")
    fake = _FakeDevice()
    adb.device = cast(Any, fake)

    image = adb.screenshot()

    assert image is fake.image
    assert fake.calls == [((), {})]


def test_screenshot_lossless_true_uses_display_id_zero():
    """lossless=True 时应走 display_id=0 无损路径。"""
    adb = AdbController("127.0.0.1:5555")
    fake = _FakeDevice()
    adb.device = cast(Any, fake)

    image = adb.screenshot(lossless=True)

    assert image is fake.image
    assert fake.calls == [((), {"display_id": 0})]
