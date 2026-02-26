# -*- coding: utf-8 -*-
"""
ADB 控制器模块

封装 uiautomator2 操作（截图、点击、滑动等）。
"""

import io
import logging
import time
from pathlib import Path
from typing import Optional, Tuple

import uiautomator2 as u2
from PIL import Image

from ptcgp_auto_v2.config.constants import (
    ADB_CONNECT_FAIL_RESTART_THRESHOLD,
    DEFAULT_ADB_PORT,
    DEFAULT_LONG_PRESS_STEPS,
    DEFAULT_SWIPE_STEPS,
)
from ptcgp_auto_v2.config.settings import get_settings
from ptcgp_auto_v2.utils.bluestacks_manager import (
    restart_bluestacks_instance_for_device,
    wait_for_bluestacks_port,
)

logger = logging.getLogger(__name__)


class AdbController:
    """
    ADB 设备控制器

    封装与 Android 模拟器的交互操作。
    """

    _connect_failures: dict[str, int] = {}

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
            self.port = DEFAULT_ADB_PORT

        # 从 settings 获取配置
        settings = get_settings()

        self.device: Optional[u2.Device] = None

        # 基准分辨率（用于坐标比例计算）
        self.base_width = settings.base_screen_width
        self.base_height = settings.base_screen_height

        # 当前分辨率（连接后通过 window_size 更新）
        self.screen_width = settings.base_screen_width
        self.screen_height = settings.base_screen_height

        self.wait_after_click = settings.wait_after_click

        # Root 状态缓存
        self._is_rooted: Optional[bool] = None

    def is_rooted(self) -> bool:
        """
        检查设备是否已 Root（带缓存）

        Returns:
            True 表示已 Root
        """
        if self._is_rooted is not None:
            return self._is_rooted

        try:
            result = self.shell("su -c 'id'")
            self._is_rooted = result is not None and "uid=0" in result
        except (RuntimeError, OSError):
            self._is_rooted = False

        # 记录日志但不频繁打印
        if self._is_rooted:
            logger.debug(f"设备 Root 状态: {self._is_rooted}")

        return self._is_rooted

    def run_as_root(self, command: str) -> Optional[str]:
        """
        以 Root 权限执行命令

        Args:
            command: 要执行的命令

        Returns:
            命令输出，失败返回 None
        """
        if not self.is_rooted():
            logger.warning(f"设备未 Root，无法以 Root 权限执行: {command}")
            return None

        # 对命令中的单引号进行转义，防止破坏 su -c '...' 结构
        safe_command = command.replace("'", "'\\''")
        return self.shell(f"su -c '{safe_command}'")

    def connect(self) -> bool:
        """
        连接到 ADB 设备

        Returns:
            True 表示连接成功
        """
        try:
            self.device = u2.connect(self.address)
            if not self.is_connected():
                logger.error(f"u2 连接失败: {self.address}")
                if self._register_connect_failure():
                    return self._retry_connect_after_restart()
                return False

            logger.info(f"已连接设备: {self.address}")

            # 自动获取屏幕分辨率
            self._update_screen_size()
            self._reset_connect_failures()

            return True

        except (RuntimeError, ConnectionError, OSError) as e:
            logger.error(f"u2 连接失败: {e}")
            if self._register_connect_failure():
                return self._retry_connect_after_restart()
            return False

    def disconnect(self):
        """断开 ADB 连接"""
        if self.device:
            self.device = None
            logger.info("设备连接已断开")

    def _register_connect_failure(self) -> bool:
        """记录连接失败并在必要时重启模拟器。"""
        failures = self._connect_failures.get(self.address, 0) + 1
        self._connect_failures[self.address] = failures
        logger.warning(
            "ADB 连续失败次数: %s/%s (%s)",
            failures,
            ADB_CONNECT_FAIL_RESTART_THRESHOLD,
            self.address,
        )
        if failures >= ADB_CONNECT_FAIL_RESTART_THRESHOLD:
            logger.warning("超过连接失败阈值，尝试重启模拟器: %s", self.address)
            restart_bluestacks_instance_for_device(self.address)
            self._connect_failures[self.address] = 0
            return True
        return False

    def _retry_connect_after_restart(self) -> bool:
        """重启后等待端口就绪并重试连接。"""
        if not wait_for_bluestacks_port(self.address, timeout_seconds=90):
            return False

        for attempt in range(1, 6):
            try:
                self.device = u2.connect(self.address)
                if not self.is_connected():
                    time.sleep(2.0)
                    continue
                logger.info(f"已连接设备: {self.address}")
                self._update_screen_size()
                self._reset_connect_failures()
                return True
            except (RuntimeError, ConnectionError, OSError) as e:
                logger.error(f"u2 重试连接失败: {e}")
                time.sleep(2.0)

        return False

    def _reset_connect_failures(self):
        """重置连接失败计数。"""
        if self.address in self._connect_failures:
            self._connect_failures[self.address] = 0

    def _update_screen_size(self):
        """获取并更新屏幕分辨率"""
        if not self.device:
            return

        try:
            width, height = self.device.window_size()
            self.screen_width = int(width)
            self.screen_height = int(height)
            logger.info(f"屏幕分辨率: {self.screen_width}x{self.screen_height}")
        except (RuntimeError, ValueError, OSError) as e:
            logger.warning(f"获取屏幕分辨率失败，使用基准值: {e}")

    @property
    def scale_x(self) -> float:
        """X 轴缩放比例（当前分辨率 / 基准分辨率）"""
        return self.screen_width / self.base_width

    @property
    def scale_y(self) -> float:
        """Y 轴缩放比例（当前分辨率 / 基准分辨率）"""
        return self.screen_height / self.base_height

    def scaled_x(self, x: int) -> int:
        """根据屏幕宽度缩放 X 坐标（基于基准宽度）"""
        return int(x * self.scale_x)

    def scaled_y(self, y: int) -> int:
        """根据屏幕高度缩放 Y 坐标（基于基准高度）"""
        return int(y * self.scale_y)

    def center_x(self) -> int:
        """返回当前屏幕中心x位置"""
        return self.screen_width // 2

    def center_y(self) -> int:
        """返回当前屏幕中心y位置"""
        return self.screen_height // 2

    def scaled_point(self, x: int, y: int) -> tuple[int, int]:
        """缩放坐标点"""
        return self.scaled_x(x), self.scaled_y(y)

    def is_connected(self) -> bool:
        """检查设备是否已连接"""
        if not self.device:
            return False
        try:
            self.device.shell("echo ok")
            return True
        except Exception:
            return False

    def screenshot(self, lossless: bool = False) -> Optional[Image.Image]:
        """
        截取屏幕截图

        Args:
            lossless: 是否使用无损截图（display_id=0）

        Returns:
            PIL Image 对象，失败返回 None
        """
        if not self.device:
            logger.error("设备未连接")
            return None

        try:
            if lossless:
                result = self.device.screenshot(display_id=0)
            else:
                result = self.device.screenshot()
            if isinstance(result, Image.Image):
                return result
            logger.error("截图返回类型异常")
            return None
        except (RuntimeError, OSError, ValueError) as e:
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
            logger.debug("点击: (%s, %s)", x, y)
            time.sleep(self.wait_after_click)

        except (RuntimeError, OSError) as e:
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

    def long_press(self, x: int, y: int, steps: int = DEFAULT_LONG_PRESS_STEPS):
        """
        长按屏幕指定位置

        Args:
            x, y: 坐标
            steps: 按住步数（步数越多越久）
        """
        if not self.device:
            logger.error("设备未连接")
            return

        try:
            resolved_steps = max(1, int(steps))
            duration_seconds = self._steps_to_duration_seconds(resolved_steps)
            self.device.long_click(x, y, duration=duration_seconds)
            logger.debug("长按: (%s, %s) steps=%s", x, y, resolved_steps)
            time.sleep(self.wait_after_click)

        except (RuntimeError, OSError) as e:
            logger.error(f"长按失败: {e}")

    def swipe(
        self, x1: int, y1: int, x2: int, y2: int, steps: int = DEFAULT_SWIPE_STEPS
    ):
        """
        滑动屏幕

        Args:
            x1, y1: 起始坐标
            x2, y2: 结束坐标
            steps: 滑动步数（步数越少越快）
        """
        if not self.device:
            logger.error("设备未连接")
            return

        try:
            resolved_steps = max(1, int(steps))
            self.device.swipe(x1, y1, x2, y2, steps=resolved_steps)
            logger.debug(
                "滑动: (%s, %s) -> (%s, %s) steps=%s",
                x1,
                y1,
                x2,
                y2,
                resolved_steps,
            )
            time.sleep(self.wait_after_click)

        except (RuntimeError, OSError) as e:
            logger.error(f"滑动失败: {e}")

    def pinch_in(self, center: Tuple[int, int], scale: float, steps: int):
        """
        双指捏合缩小

        Args:
            center: 中心点坐标（当前分辨率）
            scale: 捏合幅度比例（相对屏幕短边）
            steps: 手势步数（步数越少越快）
        """
        self._perform_pinch(center=center, scale=scale, steps=steps, direction="in")

    def pinch_out(self, center: Tuple[int, int], scale: float, steps: int):
        """
        双指放大

        Args:
            center: 中心点坐标（当前分辨率）
            scale: 放大幅度比例（相对屏幕短边）
            steps: 手势步数（步数越少越快）
        """
        self._perform_pinch(center=center, scale=scale, steps=steps, direction="out")

    def _perform_pinch(
        self, center: Tuple[int, int], scale: float, steps: int, direction: str
    ):
        """
        执行双指缩放手势

        流程：
        1. 使用 u2 官方 pinch 接口执行缩放
        """
        if not self.device:
            logger.error("设备未连接")
            return

        try:
            resolved_steps = max(2, int(steps))
            resolved_scale = max(0.05, min(1.0, float(scale)))
            percent = int(round(resolved_scale * 100))
            ui_object = self.device() if callable(self.device) else self.device
            if direction == "in":
                ui_object.pinch_in(percent=percent, steps=resolved_steps)
            else:
                ui_object.pinch_out(percent=percent, steps=resolved_steps)
            logger.debug(
                "双指%s: center=%s scale=%s steps=%s",
                "缩小" if direction == "in" else "放大",
                center,
                resolved_scale,
                resolved_steps,
            )
            time.sleep(self.wait_after_click)
        except Exception as e:
            logger.error(f"双指手势失败: {e}")

    def _steps_to_duration_seconds(self, steps: int) -> float:
        """
        将滑动步数换算为 u2 期望的滑动耗时

        Args:
            steps: 滑动步数

        Returns:
            估算的滑动耗时（秒）
        """
        return max(1, steps) * 0.005

    def press_back(self):
        """按返回键"""
        if not self.device:
            logger.error("设备未连接")
            return

        try:
            self.device.press("back")
            logger.debug("按下返回键")
            time.sleep(self.wait_after_click)

        except (RuntimeError, OSError) as e:
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
            result = self.device.shell(command)
            if hasattr(result, "output"):
                return result.output
            if result is None:
                return None
            return str(result)
        except (RuntimeError, OSError) as e:
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
        except (RuntimeError, OSError) as e:
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
            self.device.pull(remote_path, local_path)
            logger.debug(f"拉取文件: {remote_path} -> {local_path}")
            return True
        except (RuntimeError, OSError, FileNotFoundError) as e:
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
            self.device.app_stop(package_name)
            logger.debug(f"已强制停止应用: {package_name}")
        except (RuntimeError, OSError) as e:
            logger.error(f"停止应用失败: {e}")

    def start_app(self, package_name: str, activity: Optional[str] = None):
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
                self.device.app_start(package_name, activity)
            else:
                self.device.app_start(package_name, use_monkey=True)
            logger.debug(f"已启动应用: {package_name}")
        except (RuntimeError, OSError) as e:
            logger.error(f"启动应用失败: {e}")

    def restart_app(
        self,
        package_name: str,
        activity: Optional[str] = None,
        wait_time: float = 2.0,
    ):
        """
        重启应用

        Args:
            package_name: 应用包名
            activity: Activity 名称（可选）
            wait_time: 停止后等待时间（秒）
        """
        self.force_stop(package_name)
        time.sleep(wait_time)
        self.start_app(package_name, activity)
