# -*- coding: utf-8 -*-
"""
测试桩：模拟 AdbController 与 u2 设备接口。
"""

from typing import Optional, Tuple


class FakeU2Device:
    """模拟 uiautomator2 设备接口。"""

    def __init__(
        self,
        adb=None,
        screen_size: Tuple[int, int] = (1080, 1920),
        screenshot_image=None,
    ):
        """初始化模拟设备。"""
        self._adb = adb
        self._screen_width, self._screen_height = screen_size
        self._screenshot_image = screenshot_image
        self.clicks = []
        self.swipes = []
        self.presses = []
        self.long_clicks = []
        self.sent_keys = []
        self.app_starts = []
        self.app_stops = []
        self.shell_commands = []
        self.gestures = []

    def click(self, x: int, y: int) -> None:
        """记录点击坐标。"""
        self.clicks.append((x, y))
        if self._adb:
            self._adb._record_tap(x, y)

    def swipe(self, x1: int, y1: int, x2: int, y2: int, steps: int = 0) -> None:
        """记录滑动轨迹。"""
        self.swipes.append(((x1, y1), (x2, y2), steps))

    def gesture(self, *paths, **kwargs) -> None:
        """记录双指手势轨迹。"""
        self.gestures.append((paths, kwargs))

    def screenshot(self):
        """返回模拟截图。"""
        return self._screenshot_image

    def window_size(self) -> Tuple[int, int]:
        """返回屏幕尺寸。"""
        return self._screen_width, self._screen_height

    def press(self, key: str) -> None:
        """记录按键事件。"""
        self.presses.append(key)

    def send_keys(self, text: str) -> None:
        """记录输入文本。"""
        self.sent_keys.append(text)
        if self._adb is not None:
            self._adb.inputs.append(text)

    def clear_text(self) -> None:
        """模拟清空输入框。"""
        self.sent_keys.append("")

    def long_click(self, x: int, y: int, duration: float = 0.0) -> None:
        """记录长按动作。"""
        self.long_clicks.append((x, y, duration))

    def app_start(self, package_name: str, activity: Optional[str] = None, **kwargs):
        """记录启动应用。"""
        self.app_starts.append((package_name, activity, kwargs))

    def app_stop(self, package_name: str) -> None:
        """记录停止应用。"""
        self.app_stops.append(package_name)

    def shell(self, command: str):
        """记录 shell 命令并返回固定结果。"""
        self.shell_commands.append(command)
        return "ok"


class FakeAdb:
    """模拟 AdbController 行为。"""

    def __init__(
        self,
        screen_width: int = 1080,
        screen_height: int = 1920,
        screenshot_image=None,
    ):
        """初始化模拟控制器。"""
        self.taps = []
        self.tap_points = []
        self.swipes = []
        self.long_presses = []
        self.inputs = []
        self.keyevents = []
        self.back_count = 0
        self.pinch_actions = []
        self._screen_width = screen_width
        self._screen_height = screen_height
        self._device = FakeU2Device(
            adb=self,
            screen_size=(screen_width, screen_height),
            screenshot_image=screenshot_image,
        )

    def _record_tap(self, x: int, y: int) -> None:
        """记录点击坐标。"""
        self.tap_points.append((x, y))

    @property
    def device(self) -> FakeU2Device:
        """返回模拟设备对象。"""
        return self._device

    @property
    def screen_width(self) -> int:
        """返回屏幕宽度。"""
        return self._screen_width

    @property
    def screen_height(self) -> int:
        """返回屏幕高度。"""
        return self._screen_height

    def tap(self, x: int, y: int) -> None:
        """记录点击。"""
        self._record_tap(x, y)

    def click(self, x: int, y: int) -> None:
        """模拟点击（与 tap 兼容）。"""
        self._device.click(x, y)

    def tap_center(self, box) -> None:
        """点击边界框中心。"""
        resolved_box = box.box if hasattr(box, "box") else box
        if isinstance(resolved_box, dict):
            x = (resolved_box["x1"] + resolved_box["x2"]) // 2
            y = (resolved_box["y1"] + resolved_box["y2"]) // 2
            self.taps.append(
                (
                    resolved_box["x1"],
                    resolved_box["y1"],
                    resolved_box["x2"],
                    resolved_box["y2"],
                )
            )
        elif isinstance(resolved_box, (tuple, list)):
            x = (resolved_box[0] + resolved_box[2]) // 2
            y = (resolved_box[1] + resolved_box[3]) // 2
            self.taps.append(tuple(resolved_box))
        else:
            x = (resolved_box.x1 + resolved_box.x2) // 2
            y = (resolved_box.y1 + resolved_box.y2) // 2
            self.taps.append(resolved_box)
        self._record_tap(x, y)

    def long_press(self, x: int, y: int, steps: int = 1) -> None:
        """记录长按步数。"""
        self.long_presses.append((x, y, steps))

    def long_click(self, x: int, y: int, duration: float = 0.0) -> None:
        """模拟设备长按。"""
        self._device.long_click(x, y, duration=duration)

    def swipe(self, x1: int, y1: int, x2: int, y2: int, steps: int = 0) -> None:
        """记录滑动动作。"""
        self.swipes.append(((x1, y1), (x2, y2), steps))
        self._device.swipe(x1, y1, x2, y2, steps=steps)

    def pinch_in(self, center, scale: float, steps: int) -> None:
        """记录双指捏合参数。"""
        self.pinch_actions.append(("in", center, scale, steps))

    def pinch_out(self, center, scale: float, steps: int) -> None:
        """记录双指放大参数。"""
        self.pinch_actions.append(("out", center, scale, steps))

    def screenshot(self, lossless: bool = False):
        """获取模拟截图。"""
        return self._device.screenshot()

    def window_size(self) -> Tuple[int, int]:
        """获取屏幕尺寸。"""
        return self._device.window_size()

    def shell(self, command: str):
        """执行模拟 shell 命令。"""
        return self._device.shell(command)

    def press(self, key: str) -> None:
        """记录按键事件。"""
        self._device.press(key)

    def press_back(self) -> None:
        """模拟返回键。"""
        self.back_count += 1
        self.press("back")

    def send_keys(self, text: str) -> None:
        """记录输入文本。"""
        self._device.send_keys(text)

    def app_start(self, package_name: str, activity: Optional[str] = None, **kwargs):
        """记录启动应用。"""
        self._device.app_start(package_name, activity, **kwargs)

    def app_stop(self, package_name: str) -> None:
        """记录停止应用。"""
        self._device.app_stop(package_name)

    def input_text(self, text: str) -> None:
        """兼容旧输入接口。"""
        self.send_keys(text)

    def scaled_x(self, x: int) -> int:
        """按基准宽度缩放 X 坐标。"""
        return int(x * self._screen_width / 1080)

    def scaled_y(self, y: int) -> int:
        """按基准高度缩放 Y 坐标。"""
        return int(y * self._screen_height / 1920)

    def center_x(self) -> int:
        """返回屏幕中心 X。"""
        return self._screen_width // 2

    def center_y(self) -> int:
        """返回屏幕中心 Y。"""
        return self._screen_height // 2
