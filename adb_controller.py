"""
ADB 控制器 - 封装 ADB 操作（截图、点击、滑动）
"""

import io
import time
from pathlib import Path
from typing import Optional, Tuple

from adbutils import adb, AdbDevice
from PIL import Image

import config
from utils import get_data_dir


class AdbController:
    """ADB 设备控制器"""

    def __init__(self, host: str = None, port: int = None):
        self.host = host or config.ADB_HOST
        self.port = port or config.ADB_PORT
        self.device: Optional[AdbDevice] = None
        # 使用统一的数据目录
        self.data_dir = get_data_dir(self.port)

    def connect(self) -> bool:
        """连接到 ADB 设备"""
        try:
            addr = f"{self.host}:{self.port}"
            output = adb.connect(addr)
            print(f"ADB 连接: {output}")

            # 获取指定地址的设备
            self.device = adb.device(serial=addr)
            print(f"已连接设备: {self.device.serial}")

            # 自动获取屏幕分辨率
            self._update_screen_size()

            return True

        except Exception as e:
            print(f"ADB 连接失败: {e}")
            return False

    def _update_screen_size(self):
        """获取并更新屏幕分辨率到 config"""
        if not self.device:
            return

        try:
            # 执行 wm size 获取屏幕尺寸
            output = self.device.shell("wm size")
            # 输出格式: "Physical size: 1080x1920" 或 "Override size: ..."
            # 优先使用 Override size（如果有的话）
            lines = output.strip().split('\n')
            size_str = None
            for line in lines:
                if 'Override size:' in line:
                    size_str = line.split(':')[1].strip()
                    break
            if not size_str:
                for line in lines:
                    if 'Physical size:' in line:
                        size_str = line.split(':')[1].strip()
                        break

            if size_str:
                width, height = map(int, size_str.split('x'))
                config.SCREEN_WIDTH = width
                config.SCREEN_HEIGHT = height
                print(f"屏幕分辨率: {width}x{height}")
        except Exception as e:
            print(f"获取屏幕分辨率失败，使用默认值: {e}")

    def disconnect(self):
        """断开 ADB 连接"""
        if self.device:
            try:
                adb.disconnect(f"{self.host}:{self.port}")
                print("ADB 已断开")
            except Exception as e:
                print(f"断开失败: {e}")

    def screenshot(self) -> Optional[Image.Image]:
        """截取屏幕截图"""
        if not self.device:
            print("错误: 设备未连接")
            return None

        try:
            # 使用 adbutils 的截图功能
            result = self.device.screenshot()

            # adbutils 可能返回 PIL Image 或 bytes，需要兼容处理
            if isinstance(result, Image.Image):
                return result
            elif isinstance(result, bytes):
                return Image.open(io.BytesIO(result))
            else:
                # 尝试作为 bytes 处理
                return Image.open(io.BytesIO(bytes(result)))

        except Exception as e:
            print(f"截图失败: {e}")
            return None

    def tap(self, x: int, y: int):
        """点击屏幕指定位置"""
        if not self.device:
            print("错误: 设备未连接")
            return

        try:
            self.device.click(x, y)
            if config.DEBUG:
                print(f"点击: ({x}, {y})")
            time.sleep(config.WAIT_AFTER_CLICK)

        except Exception as e:
            print(f"点击失败: {e}")

    def tap_center(self, box: Tuple[int, int, int, int]):
        """点击矩形区域的中心点

        Args:
            box: (x1, y1, x2, y2) 矩形区域
        """
        x = (box[0] + box[2]) // 2
        y = (box[1] + box[3]) // 2
        self.tap(x, y)

    def swipe(self, x1: int, y1: int, x2: int, y2: int, duration: int = 300):
        """滑动屏幕

        Args:
            x1, y1: 起始坐标
            x2, y2: 结束坐标
            duration: 滑动持续时间（毫秒）
        """
        if not self.device:
            print("错误: 设备未连接")
            return

        try:
            self.device.swipe(x1, y1, x2, y2, duration / 1000)
            if config.DEBUG:
                print(f"滑动: ({x1}, {y1}) -> ({x2}, {y2})")
            time.sleep(config.WAIT_AFTER_CLICK)

        except Exception as e:
            print(f"滑动失败: {e}")

    def swipe_up(self, ratio: float = 0.26, duration: int = 500):
        """向上滑动（用于查看更多内容）

        Args:
            ratio: 滑动距离占屏幕高度的比例（默认 0.26 约等于 1920 下的 500px）
            duration: 滑动持续时间（毫秒），越大越慢
        """
        distance = int(config.SCREEN_HEIGHT * ratio)
        center_x = config.SCREEN_WIDTH // 2
        start_y = config.SCREEN_HEIGHT // 2 + distance // 2
        end_y = config.SCREEN_HEIGHT // 2 - distance // 2
        self.swipe(center_x, start_y, center_x, end_y, duration)

    def swipe_down(self, ratio: float = 0.26, duration: int = 500):
        """向下滑动

        Args:
            ratio: 滑动距离占屏幕高度的比例（默认 0.26 约等于 1920 下的 500px）
            duration: 滑动持续时间（毫秒），越大越慢
        """
        distance = int(config.SCREEN_HEIGHT * ratio)
        center_x = config.SCREEN_WIDTH // 2
        start_y = config.SCREEN_HEIGHT // 2 - distance // 2
        end_y = config.SCREEN_HEIGHT // 2 + distance // 2
        self.swipe(center_x, start_y, center_x, end_y, duration)

    def back(self):
        """按返回键"""
        if not self.device:
            print("错误: 设备未连接")
            return

        try:
            self.device.keyevent(4)  # KEYCODE_BACK
            if config.DEBUG:
                print("按下返回键")
            time.sleep(config.WAIT_AFTER_CLICK)

        except Exception as e:
            print(f"返回键失败: {e}")

    def save_screenshot(self, filename: str) -> Optional[str]:
        """保存截图到文件（用于调试）"""
        image = self.screenshot()
        if image:
            filepath = self.data_dir / filename
            image.save(filepath)
            print(f"截图已保存: {filepath}")
            return str(filepath)
        return None


# 便捷的全局实例
_controller: Optional[AdbController] = None


def get_controller() -> AdbController:
    """获取全局 ADB 控制器实例"""
    global _controller
    if _controller is None:
        _controller = AdbController()
    return _controller
