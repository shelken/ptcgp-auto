# -*- coding: utf-8 -*-
"""
ADB 控制器模块

封装 uiautomator2 操作（截图、点击、滑动等）。
"""

import logging
import time
from typing import Optional, Tuple

import uiautomator2 as u2
from adbutils import adb
from adbutils.errors import AdbError
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
        self._dependency_broken_reason: Optional[str] = None

    def _require_device(self) -> u2.Device:
        if self._dependency_broken_reason is not None:
            raise RuntimeError(self._dependency_broken_reason)
        if not self.device:
            logger.error("设备未连接: %s", self.address)
            raise RuntimeError(f"设备未连接: {self.address}")
        return self.device

    def _connect_device(self, operation: str):
        """之前连接阶段会把可恢复的服务占用错误直接抛出。现在在当前线程执行 u2.connect，并在可恢复的 ADB 或无障碍竞态上先修复 transport 再重试。这样可以避免把临时断链误判成设备失活。"""
        for attempt in range(1, 4):
            try:
                return u2.connect(self.address)
            except Exception as exc:
                if not self._should_retry_connect(exc):
                    raise
                if attempt == 3:
                    raise
                if self._should_refresh_transport(exc):
                    self._refresh_adb_transport(operation)
                logger.warning(
                    "u2 服务启动未稳定，等待后重试: %s (%s)",
                    self.address,
                    operation,
                )
                time.sleep(1.0)
        raise RuntimeError(f"u2 连接重试失败: {self.address}")

    @staticmethod
    def _should_retry_connect(exc: Exception) -> bool:
        """之前只重试单一无障碍占用错误。现在会把 transport 被关闭、设备短暂失联和 uiautomator 启动竞态一并视为可恢复错误。这样连接阶段会先自愈再决定是否失败。"""
        if isinstance(exc, u2.exceptions.AccessibilityServiceAlreadyRegisteredError):
            return True
        if isinstance(exc, AdbError):
            return True
        message = str(exc)
        transient_markers = (
            "server quit unexpectly",
            "UiAutomation not connected",
            "NullPointerException",
            "AccessibilityServiceAlreadyRegisteredError",
            "closed",
            "not found",
        )
        return any(marker in message for marker in transient_markers)

    @staticmethod
    def _should_refresh_transport(exc: Exception) -> bool:
        """之前所有连接重试都只做等待。现在仅在 transport 断链类错误上执行 ADB 刷新。这样无障碍服务竞态不会被误处理成断线重连。"""
        if isinstance(exc, AdbError):
            return True
        message = str(exc)
        refresh_markers = (
            "server quit unexpectly",
            "UiAutomation not connected",
            "closed",
            "not found",
        )
        return any(marker in message for marker in refresh_markers)

    def _refresh_adb_transport(self, operation: str):
        """之前连接重试不会修复旧 transport。现在会先断开再重连当前地址。这样 `adbutils.errors.AdbError: closed` 这类断链能在下一次 u2.connect 前收敛。"""
        try:
            disconnect_result = adb.disconnect(self.address, raise_error=False)
            logger.warning(
                "ADB transport 刷新: disconnect %s (%s) -> %s",
                self.address,
                operation,
                disconnect_result,
            )
        except Exception as exc:
            logger.warning(
                "ADB transport 断开失败，继续尝试重连: %s (%s) err=%s",
                self.address,
                operation,
                exc,
            )
        try:
            connect_result = adb.connect(self.address)
            logger.warning(
                "ADB transport 刷新: connect %s (%s) -> %s",
                self.address,
                operation,
                connect_result,
            )
        except Exception as exc:
            logger.warning(
                "ADB transport 重连失败: %s (%s) err=%s",
                self.address,
                operation,
                exc,
            )

    def _call_device(
        self,
        operation: str,
        func,
    ):
        """之前设备调用复用后台线程超时包装。现在直接在当前线程执行 uiautomator2 调用，因为后台线程会把截图与 shell 等调用误打成超时。这样能保证执行链路与手工直连一致。"""
        del operation
        return func()

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
        except (RuntimeError, OSError, AdbError):
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
            self.device = self._connect_device("u2.connect")
            self._dependency_broken_reason = None
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

        except (RuntimeError, ConnectionError, OSError, AdbError) as e:
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
        """之前达到阈值就直接重启模拟器。现在会先做设备健康检查，只在确认实例失活后才允许重启。这样可以避免因为短暂 ADB 断链频繁重启实例。"""
        failures = self._connect_failures.get(self.address, 0) + 1
        self._connect_failures[self.address] = failures
        logger.warning(
            "ADB 连续失败次数: %s/%s (%s)",
            failures,
            ADB_CONNECT_FAIL_RESTART_THRESHOLD,
            self.address,
        )
        if failures >= ADB_CONNECT_FAIL_RESTART_THRESHOLD:
            if not self._should_restart_emulator():
                logger.warning("设备健康检查通过，跳过模拟器重启: %s", self.address)
                self._connect_failures[self.address] = 0
                return False
            logger.warning("超过连接失败阈值，尝试重启模拟器: %s", self.address)
            restart_bluestacks_instance_for_device(self.address)
            self._connect_failures[self.address] = 0
            return True
        return False

    def _should_restart_emulator(self) -> bool:
        """之前重启前不验证实例是否真的失活。现在先检查端口和 ADB shell 健康。这样只有实例无法自愈时才会消耗一次重启。"""
        if not wait_for_bluestacks_port(self.address, timeout_seconds=3, interval_seconds=1.0):
            logger.warning("模拟器端口未就绪，允许重启: %s", self.address)
            return True
        try:
            adb.connect(self.address)
            device = adb.device(serial=self.address)
            device.shell(["echo", "ok"])
        except Exception as exc:
            logger.warning("设备健康检查失败，允许重启: %s err=%s", self.address, exc)
            return True
        return False

    def _retry_connect_after_restart(self) -> bool:
        """重启后等待端口就绪并重试连接。"""
        if not wait_for_bluestacks_port(self.address, timeout_seconds=90):
            return False

        for attempt in range(1, 6):
            try:
                self.device = self._connect_device(f"u2.connect.retry#{attempt}")
                self._dependency_broken_reason = None
                if not self.is_connected():
                    time.sleep(2.0)
                    continue
                logger.info(f"已连接设备: {self.address}")
                self._update_screen_size()
                self._reset_connect_failures()
                return True
            except (RuntimeError, ConnectionError, OSError, AdbError) as e:
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

        width, height = self._call_device(
            "window_size",
            lambda: self._require_device().window_size(),
        )
        self.screen_width = int(width)
        self.screen_height = int(height)
        logger.info(f"屏幕分辨率: {self.screen_width}x{self.screen_height}")

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

    def is_connected(self) -> bool:
        """检查设备是否已连接"""
        if not self.device:
            return False
        try:
            self._call_device(
                "shell.echo_ok",
                lambda: self._require_device().shell("echo ok"),
            )
            return True
        except (RuntimeError, OSError, AdbError):
            return False

    def screenshot(self, lossless: bool = False) -> Optional[Image.Image]:
        """
        截取屏幕截图

        Args:
            lossless: 是否使用无损截图（display_id=0）

        Returns:
            PIL Image 对象，失败返回 None
        """
        if lossless:
            result = self._call_device(
                "screenshot.lossless",
                lambda: self._require_device().screenshot(display_id=0),
            )
        else:
            result = self._call_device(
                "screenshot",
                lambda: self._require_device().screenshot(),
            )
        if not isinstance(result, Image.Image):
            logger.error("截图返回类型异常: type=%s", type(result).__name__)
            raise RuntimeError(f"截图返回类型异常: {type(result).__name__}")
        return result

    def tap(self, x: int, y: int):
        """
        点击屏幕指定位置

        Args:
            x, y: 点击坐标
        """
        self._call_device(
            f"click({x},{y})",
            lambda: self._require_device().click(x, y),
        )
        logger.debug("点击: (%s, %s)", x, y)
        time.sleep(self.wait_after_click)

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
        resolved_steps = max(1, int(steps))
        duration_seconds = self._steps_to_duration_seconds(resolved_steps)
        self._call_device(
            f"long_click({x},{y})",
            lambda: self._require_device().long_click(x, y, duration=duration_seconds),
        )
        logger.debug("长按: (%s, %s) steps=%s", x, y, resolved_steps)
        time.sleep(self.wait_after_click)

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
        resolved_steps = max(1, int(steps))
        self._call_device(
            f"swipe({x1},{y1})->({x2},{y2})",
            lambda: self._require_device().swipe(x1, y1, x2, y2, steps=resolved_steps),
        )
        logger.debug(
            "滑动: (%s, %s) -> (%s, %s) steps=%s",
            x1,
            y1,
            x2,
            y2,
            resolved_steps,
        )
        time.sleep(self.wait_after_click)

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
        resolved_steps = max(2, int(steps))
        resolved_scale = max(0.05, min(1.0, float(scale)))
        percent = int(round(resolved_scale * 100))

        def _pinch():
            device = self._require_device()
            ui_object = device() if callable(device) else device
            if direction == "in":
                ui_object.pinch_in(percent=percent, steps=resolved_steps)
            else:
                ui_object.pinch_out(percent=percent, steps=resolved_steps)

        self._call_device(
            f"pinch_{direction}(percent={percent},steps={resolved_steps})",
            _pinch,
        )
        logger.debug(
            "双指%s: center=%s scale=%s steps=%s",
            "缩小" if direction == "in" else "放大",
            center,
            resolved_scale,
            resolved_steps,
        )
        time.sleep(self.wait_after_click)

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
        self._call_device(
            "press(back)",
            lambda: self._require_device().press("back"),
        )
        logger.debug("按下返回键")
        time.sleep(self.wait_after_click)

    def shell(self, command: str) -> Optional[str]:
        """
        执行 adb shell 命令

        Args:
            command: Shell 命令

        Returns:
            命令输出，失败返回 None
        """
        result = self._call_device(
            f"shell({command})",
            lambda: self._require_device().shell(command),
        )
        if hasattr(result, "output"):
            output = result.output
            return "" if output is None else str(output)
        if result is None:
            return ""
        return str(result)

    def push(self, local_path: str, remote_path: str) -> bool:
        """
        推送文件到设备

        Args:
            local_path: 本地文件路径
            remote_path: 设备上的目标路径

        Returns:
            True 表示成功
        """
        self._call_device(
            f"push({local_path}->{remote_path})",
            lambda: self._require_device().push(local_path, remote_path),
        )
        logger.debug(f"推送文件: {local_path} -> {remote_path}")
        return True

    def pull(self, remote_path: str, local_path: str) -> bool:
        """
        从设备拉取文件

        Args:
            remote_path: 设备上的文件路径
            local_path: 本地目标路径

        Returns:
            True 表示成功
        """
        self._call_device(
            f"pull({remote_path}->{local_path})",
            lambda: self._require_device().pull(remote_path, local_path),
        )
        logger.debug(f"拉取文件: {remote_path} -> {local_path}")
        return True

    def force_stop(self, package_name: str):
        """
        强制停止应用

        Args:
            package_name: 应用包名
        """
        self._call_device(
            f"app_stop({package_name})",
            lambda: self._require_device().app_stop(package_name),
        )
        logger.debug(f"已强制停止应用: {package_name}")

    def start_app(self, package_name: str, activity: Optional[str] = None):
        """
        启动应用

        Args:
            package_name: 应用包名
            activity: Activity 名称（可选）
        """
        if activity:
            self._call_device(
                f"app_start({package_name},{activity})",
                lambda: self._require_device().app_start(package_name, activity),
            )
        else:
            self._call_device(
                f"app_start({package_name})",
                lambda: self._require_device().app_start(
                    package_name, use_monkey=True
                ),
            )
        logger.debug(f"已启动应用: {package_name}")

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
