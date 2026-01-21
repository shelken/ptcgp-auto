# -*- coding: utf-8 -*-
"""
ADB 控制器模块

封装 ADB 操作（截图、点击、滑动等）。
"""

import io
import logging
import time
from pathlib import Path
from typing import Optional, Tuple

from adbutils import adb, AdbDevice
from PIL import Image

logger = logging.getLogger(__name__)

# 默认配置
DEFAULT_WAIT_AFTER_CLICK = 0.3
DEFAULT_SCREEN_WIDTH = 1080
DEFAULT_SCREEN_HEIGHT = 1920


class AdbController:
    """
    ADB 设备控制器

    封装与 Android 模拟器的交互操作。
    """

    def __init__(self, address: str):
        """
        初始化 ADB 控制器

        Args:
            address: ADB 地址，格式为 "host:port"，如 "127.0.0.1:5555"
        """
        self.address = address
        if ":" in address:
            self.host, port_str = address.rsplit(":", 1)
            self.port = int(port_str)
        else:
            self.host = address
            self.port = 5555

        self.device: Optional[AdbDevice] = None
        self.screen_width = DEFAULT_SCREEN_WIDTH
        self.screen_height = DEFAULT_SCREEN_HEIGHT
        self.wait_after_click = DEFAULT_WAIT_AFTER_CLICK

    def connect(self) -> bool:
        """
        连接到 ADB 设备

        Returns:
            True 表示连接成功
        """
        try:
            output = adb.connect(self.address)
            logger.info(f"ADB 连接: {output}")

            self.device = adb.device(serial=self.address)
            logger.info(f"已连接设备: {self.device.serial}")

            # 自动获取屏幕分辨率
            self._update_screen_size()

            return True

        except Exception as e:
            logger.error(f"ADB 连接失败: {e}")
            return False

    def disconnect(self):
        """断开 ADB 连接"""
        if self.device:
            try:
                adb.disconnect(self.address)
                logger.info("ADB 已断开")
            except Exception as e:
                logger.error(f"断开失败: {e}")

    def _update_screen_size(self):
        """获取并更新屏幕分辨率"""
        if not self.device:
            return

        try:
            output = self.device.shell("wm size")
            lines = output.strip().split("\n")
            size_str = None

            # 优先使用 Override size
            for line in lines:
                if "Override size:" in line:
                    size_str = line.split(":")[1].strip()
                    break
            if not size_str:
                for line in lines:
                    if "Physical size:" in line:
                        size_str = line.split(":")[1].strip()
                        break

            if size_str:
                width, height = map(int, size_str.split("x"))
                self.screen_width = width
                self.screen_height = height
                logger.info(f"屏幕分辨率: {width}x{height}")

        except Exception as e:
            logger.warning(f"获取屏幕分辨率失败，使用默认值: {e}")

    def is_connected(self) -> bool:
        """检查设备是否已连接"""
        if not self.device:
            return False
        try:
            self.device.shell("echo ok")
            return True
        except Exception:
            return False

    def screenshot(self) -> Optional[Image.Image]:
        """
        截取屏幕截图

        Returns:
            PIL Image 对象，失败返回 None
        """
        if not self.device:
            logger.error("设备未连接")
            return None

        try:
            result = self.device.screenshot()

            if isinstance(result, Image.Image):
                return result
            elif isinstance(result, bytes):
                return Image.open(io.BytesIO(result))
            else:
                return Image.open(io.BytesIO(bytes(result)))

        except Exception as e:
            logger.error(f"截图失败: {e}")
            return None

    def tap(self, x: int, y: int):
        """
        点击屏幕指定位置

        Args:
            x, y: 点击坐标
        """
        if not self.device:
            logger.error("设备未连接")
            return

        try:
            self.device.click(x, y)
            logger.debug(f"点击: ({x}, {y})")
            time.sleep(self.wait_after_click)

        except Exception as e:
            logger.error(f"点击失败: {e}")

    def tap_center(self, box: Tuple[int, int, int, int]):
        """
        点击矩形区域的中心点

        Args:
            box: (x1, y1, x2, y2) 矩形区域
        """
        x = (box[0] + box[2]) // 2
        y = (box[1] + box[3]) // 2
        self.tap(x, y)

    def long_press(self, x: int, y: int, duration: int = 1000):
        """
        长按屏幕指定位置

        Args:
            x, y: 坐标
            duration: 按住时间（毫秒）
        """
        if not self.device:
            logger.error("设备未连接")
            return

        try:
            self.device.swipe(x, y, x, y, duration / 1000)
            logger.debug(f"长按: ({x}, {y}) 持续 {duration}ms")
            time.sleep(self.wait_after_click)

        except Exception as e:
            logger.error(f"长按失败: {e}")

    def swipe(self, x1: int, y1: int, x2: int, y2: int, duration: int = 300):
        """
        滑动屏幕

        Args:
            x1, y1: 起始坐标
            x2, y2: 结束坐标
            duration: 滑动持续时间（毫秒）
        """
        if not self.device:
            logger.error("设备未连接")
            return

        try:
            self.device.swipe(x1, y1, x2, y2, duration / 1000)
            logger.debug(f"滑动: ({x1}, {y1}) -> ({x2}, {y2})")
            time.sleep(self.wait_after_click)

        except Exception as e:
            logger.error(f"滑动失败: {e}")

    def swipe_up(self, ratio: float = 0.26, duration: int = 500):
        """
        向上滑动

        Args:
            ratio: 滑动距离占屏幕高度的比例
            duration: 滑动持续时间（毫秒）
        """
        distance = int(self.screen_height * ratio)
        center_x = self.screen_width // 2
        start_y = self.screen_height // 2 + distance // 2
        end_y = self.screen_height // 2 - distance // 2
        self.swipe(center_x, start_y, center_x, end_y, duration)

    def swipe_down(self, ratio: float = 0.26, duration: int = 500):
        """
        向下滑动

        Args:
            ratio: 滑动距离占屏幕高度的比例
            duration: 滑动持续时间（毫秒）
        """
        distance = int(self.screen_height * ratio)
        center_x = self.screen_width // 2
        start_y = self.screen_height // 2 - distance // 2
        end_y = self.screen_height // 2 + distance // 2
        self.swipe(center_x, start_y, center_x, end_y, duration)

    def press_back(self):
        """按返回键"""
        if not self.device:
            logger.error("设备未连接")
            return

        try:
            self.device.keyevent(4)  # KEYCODE_BACK
            logger.debug("按下返回键")
            time.sleep(self.wait_after_click)

        except Exception as e:
            logger.error(f"返回键失败: {e}")

    def shell(self, command: str) -> Optional[str]:
        """
        执行 adb shell 命令

        Args:
            command: Shell 命令

        Returns:
            命令输出，失败返回 None
        """
        if not self.device:
            logger.error("设备未连接")
            return None

        try:
            return self.device.shell(command)
        except Exception as e:
            logger.error(f"执行 shell 失败: {e}")
            return None

    def push(self, local_path: str, remote_path: str) -> bool:
        """
        推送文件到设备

        Args:
            local_path: 本地文件路径
            remote_path: 设备上的目标路径

        Returns:
            True 表示成功
        """
        if not self.device:
            logger.error("设备未连接")
            return False

        try:
            self.device.push(local_path, remote_path)
            logger.debug(f"推送文件: {local_path} -> {remote_path}")
            return True
        except Exception as e:
            logger.error(f"推送文件失败: {e}")
            return False

    def pull(self, remote_path: str, local_path: str) -> bool:
        """
        从设备拉取文件

        Args:
            remote_path: 设备上的文件路径
            local_path: 本地目标路径

        Returns:
            True 表示成功
        """
        if not self.device:
            logger.error("设备未连接")
            return False

        try:
            self.device.sync.pull(remote_path, local_path, exist_ok=True)
            logger.debug(f"拉取文件: {remote_path} -> {local_path}")
            return True
        except Exception as e:
            logger.error(f"拉取文件失败: {e}")
            return False

    def force_stop(self, package_name: str):
        """
        强制停止应用

        Args:
            package_name: 应用包名
        """
        if not self.device:
            logger.error("设备未连接")
            return

        try:
            self.device.shell(f"am force-stop {package_name}")
            logger.info(f"已强制停止应用: {package_name}")
        except Exception as e:
            logger.error(f"停止应用失败: {e}")

    def start_app(self, package_name: str, activity: str = None):
        """
        启动应用

        Args:
            package_name: 应用包名
            activity: Activity 名称（可选）
        """
        if not self.device:
            logger.error("设备未连接")
            return

        try:
            if activity:
                self.device.shell(f"am start -n {package_name}/{activity}")
            else:
                # 使用 monkey 启动主 Activity
                self.device.shell(
                    f"monkey -p {package_name} -c android.intent.category.LAUNCHER 1"
                )
            logger.info(f"已启动应用: {package_name}")
        except Exception as e:
            logger.error(f"启动应用失败: {e}")
