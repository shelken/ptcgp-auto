# -*- coding: utf-8 -*-
"""
手势工具最小单测
"""

from typing import Any, cast

from ptcgp_auto_v2.infra.adb import AdbController
from ptcgp_auto_v2.tests.fake_adb import FakeU2Device
from ptcgp_auto_v2.utils.gesture import (
    calculate_swipe_steps,
    clear_text,
    input_text,
    is_text_visible,
    normalize_text,
    quick_tap,
    scroll_points,
    tap_text_exact,
)


class DummyAdb:
    """测试用 ADB 适配器。"""

    def __init__(self, screen_width: int, screen_height: int):
        """初始化屏幕尺寸。"""
        self.screen_width = screen_width
        self.screen_height = screen_height
        self.tap_points: list[tuple[int, int]] = []

    def scaled_y(self, y: int) -> int:
        """按原值返回，便于断言。"""
        return y

    def center_x(self) -> int:
        """返回屏幕中心 X 坐标。"""
        return self.screen_width // 2

    def center_y(self) -> int:
        """返回屏幕中心 Y 坐标。"""
        return self.screen_height // 2

    def tap(self, x: int, y: int) -> None:
        """模拟点击动作。"""
        self.tap_points.append((x, y))
        return None

    def tap_center(self, box) -> None:
        """点击边界框中心，兼容真实 ADB 接口。"""
        x = (box[0] + box[2]) // 2
        y = (box[1] + box[3]) // 2
        self.tap_points.append((x, y))

    def swipe(
        self, start_x: int, start_y: int, end_x: int, end_y: int, steps: int
    ) -> None:
        """模拟滑动动作。"""
        return None


def test_normalize_text_and_match():
    """验证文本规范化与匹配逻辑。"""
    assert normalize_text("  Te st ") == "test"
    assert is_text_visible([{"text": "OK", "box": (0, 0, 10, 10)}], ["ok"], exact=True)


def test_scroll_points_up_and_down():
    """验证上滑与下滑的起止点方向。"""
    adb = DummyAdb(screen_width=1080, screen_height=1920)
    adb_controller = cast(AdbController, adb)
    start_up, end_up = scroll_points(
        adb_controller, base_distance_y=500, direction="up"
    )
    start_down, end_down = scroll_points(
        adb_controller, base_distance_y=500, direction="down"
    )
    assert start_up[1] > end_up[1]
    assert start_down[1] < end_down[1]


def test_calculate_swipe_steps_proportional():
    """验证滑动步数与距离成比例。"""
    adb = DummyAdb(screen_width=1080, screen_height=1000)
    steps = calculate_swipe_steps(cast(AdbController, adb), (0, 0), (0, 250))
    assert steps == 8


def test_calculate_swipe_steps_clamp_min():
    """验证滑动步数下限限制。"""
    adb = DummyAdb(screen_width=1080, screen_height=1000)
    steps = calculate_swipe_steps(cast(AdbController, adb), (0, 0), (0, 1))
    assert steps == 6


def test_calculate_swipe_steps_clamp_max():
    """验证滑动步数上限限制。"""
    adb = DummyAdb(screen_width=1080, screen_height=1000)
    steps = calculate_swipe_steps(cast(AdbController, adb), (0, 0), (0, 2000))
    assert steps == 24


def test_adb_no_business_gestures():
    """确认 adb 控制器不暴露业务手势。"""
    assert not hasattr(AdbController, "swipe_up")


def test_quick_tap_should_click_by_points_in_order():
    """验证 quick_tap 支持按点位列表顺序点击。"""
    adb = DummyAdb(screen_width=1080, screen_height=1920)
    result = quick_tap(
        cast(AdbController, adb),
        tap_points=[(100, 200), (300, 400), (500, 600)],
        times=1,
        wait=0.0,
    )

    assert result.ok is True
    assert adb.tap_points == [(100, 200), (300, 400), (500, 600)]


def test_tap_text_exact_should_support_pick_last():
    """验证 pick='last' 可选中最后一个同文案命中项。"""
    adb = DummyAdb(screen_width=720, screen_height=1280)

    result = tap_text_exact(
        cast(AdbController, adb),
        ocr_results=[
            {"text": "交換", "box": (100, 120, 160, 180)},
            {"text": "交換", "box": (320, 960, 400, 1040)},
            {"text": "交換", "box": (320, 880, 400, 940)},
        ],
        patterns=["交換"],
        wait=0.0,
        pick="last",
    )

    assert result is not None
    assert result.ok is True
    assert adb.tap_points == [(360, 910)]


def test_tap_text_exact_should_support_pick_index():
    """验证 pick 支持直接传索引。"""
    adb = DummyAdb(screen_width=720, screen_height=1280)

    result = tap_text_exact(
        cast(AdbController, adb),
        ocr_results=[
            {"text": "交換", "box": (100, 120, 160, 180)},
            {"text": "交換", "box": (320, 960, 400, 1040)},
            {"text": "交換", "box": (320, 880, 400, 940)},
        ],
        patterns=["交換"],
        wait=0.0,
        pick=-1,
    )

    assert result is not None
    assert result.ok is True
    assert adb.tap_points == [(360, 910)]


def _build_adb_with_fake_device():
    """构造带 FakeU2Device 的 AdbController。"""
    adb = AdbController("127.0.0.1:5555")
    fake_device = FakeU2Device(screen_size=(1080, 1920))
    adb.device = cast(Any, fake_device)
    adb.screen_width = 1080
    adb.screen_height = 1920
    return adb, fake_device


def test_pinch_out_records_gesture_points():
    """验证 pinch_out 记录双指手势参数。"""
    adb, fake_device = _build_adb_with_fake_device()
    adb.pinch_out(center=(540, 960), scale=0.2, steps=12)

    assert len(fake_device.gestures) == 1
    paths, kwargs = fake_device.gestures[0]
    assert kwargs["steps"] == 12
    assert len(paths) == 4
    for x, y in paths:
        assert 0 <= x < 1080
        assert 0 <= y < 1920


def test_pinch_in_clamps_steps_minimum():
    """验证 pinch_in 最小步数限制。"""
    adb, fake_device = _build_adb_with_fake_device()
    adb.pinch_in(center=(540, 960), scale=0.2, steps=1)

    assert len(fake_device.gestures) == 1
    _, kwargs = fake_device.gestures[0]
    assert kwargs["steps"] == 2


def test_clear_text_should_hide_fast_input_ime():
    """验证清空输入框后会显式隐藏 FastInputIME。"""
    adb, fake_device = _build_adb_with_fake_device()

    result = clear_text(adb, 320, 480, wait=0.0)

    assert result.ok is True
    assert fake_device.clicks == [(320, 480)]
    assert fake_device.shell_commands[-1] == "am broadcast -a ADB_KEYBOARD_HIDE"


def test_input_text_should_hide_fast_input_ime():
    """验证输入文本后会显式隐藏 FastInputIME。"""
    adb, fake_device = _build_adb_with_fake_device()

    result = input_text(adb, "嘎啦嘎啦", wait=0.0)

    assert result.ok is True
    assert fake_device.sent_keys == ["嘎啦嘎啦"]
    assert fake_device.shell_commands[-1] == "am broadcast -a ADB_KEYBOARD_HIDE"
