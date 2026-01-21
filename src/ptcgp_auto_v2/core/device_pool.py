# -*- coding: utf-8 -*-
"""
设备池管理模块

管理可用设备资源，支持借用和归还。
"""

import threading
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional


class DeviceStatus(Enum):
    """设备状态枚举"""
    AVAILABLE = "available"      # 空闲可用
    BUSY = "busy"                # 正在执行任务
    UNHEALTHY = "unhealthy"      # 不健康（连接失败等）


@dataclass
class Device:
    """
    设备实体

    表示一个 ADB 连接的模拟器设备。
    """
    address: str                          # ADB 地址，如 "127.0.0.1:5555"
    status: DeviceStatus = DeviceStatus.AVAILABLE
    current_account_id: Optional[int] = None  # 当前登录的账号 ID
    last_used_at: Optional[datetime] = None

    @property
    def is_available(self) -> bool:
        """检查设备是否可用"""
        return self.status == DeviceStatus.AVAILABLE

    def mark_busy(self, account_id: Optional[int] = None):
        """标记设备为忙碌状态"""
        self.status = DeviceStatus.BUSY
        self.current_account_id = account_id
        self.last_used_at = datetime.now()

    def mark_available(self):
        """标记设备为空闲状态"""
        self.status = DeviceStatus.AVAILABLE

    def mark_unhealthy(self):
        """标记设备为不健康状态"""
        self.status = DeviceStatus.UNHEALTHY


class DevicePool:
    """
    设备资源池

    管理多个设备，支持线程安全的借用和归还操作。
    设备被视为执行任务的资源，可以分配给账号使用。
    """

    def __init__(self, addresses: list[str]):
        """
        初始化设备池

        Args:
            addresses: ADB 地址列表，如 ["127.0.0.1:5555", "127.0.0.1:5556"]
        """
        self._devices: dict[str, Device] = {
            addr: Device(address=addr) for addr in addresses
        }
        self._lock = threading.Lock()

    @property
    def total_count(self) -> int:
        """总设备数"""
        return len(self._devices)

    @property
    def available_count(self) -> int:
        """可用设备数"""
        with self._lock:
            return sum(1 for d in self._devices.values() if d.is_available)

    @property
    def busy_count(self) -> int:
        """忙碌设备数"""
        with self._lock:
            return sum(1 for d in self._devices.values() if d.status == DeviceStatus.BUSY)

    def acquire(self) -> Optional[Device]:
        """
        借用一个空闲设备

        Returns:
            Device 实例，如果没有可用设备则返回 None
        """
        with self._lock:
            for device in self._devices.values():
                if device.is_available:
                    device.mark_busy()
                    return device
            return None

    def acquire_for_account(self, account_id: int) -> Optional[Device]:
        """
        为指定账号借用设备

        优先返回已登录该账号的设备，避免不必要的账号切换。

        Args:
            account_id: 账号 ID

        Returns:
            Device 实例，如果没有可用设备则返回 None
        """
        with self._lock:
            # 优先查找已登录该账号的空闲设备
            for device in self._devices.values():
                if device.is_available and device.current_account_id == account_id:
                    device.mark_busy(account_id)
                    return device

            # 其次查找任意空闲设备
            for device in self._devices.values():
                if device.is_available:
                    device.mark_busy(account_id)
                    return device

            return None

    def release(self, device: Device):
        """
        归还设备

        Args:
            device: 要归还的设备
        """
        with self._lock:
            if device.address in self._devices:
                self._devices[device.address].mark_available()

    def mark_unhealthy(self, device: Device):
        """
        标记设备为不健康

        Args:
            device: 不健康的设备
        """
        with self._lock:
            if device.address in self._devices:
                self._devices[device.address].mark_unhealthy()

    def get_device(self, address: str) -> Optional[Device]:
        """
        根据地址获取设备

        Args:
            address: ADB 地址

        Returns:
            Device 实例或 None
        """
        return self._devices.get(address)

    def get_all_devices(self) -> list[Device]:
        """获取所有设备列表"""
        return list(self._devices.values())

    def get_available_devices(self) -> list[Device]:
        """获取所有可用设备列表"""
        with self._lock:
            return [d for d in self._devices.values() if d.is_available]

    def get_status_summary(self) -> dict:
        """
        获取设备池状态摘要

        Returns:
            包含各状态设备数量的字典
        """
        with self._lock:
            summary = {
                "total": len(self._devices),
                "available": 0,
                "busy": 0,
                "unhealthy": 0,
            }
            for device in self._devices.values():
                if device.status == DeviceStatus.AVAILABLE:
                    summary["available"] += 1
                elif device.status == DeviceStatus.BUSY:
                    summary["busy"] += 1
                elif device.status == DeviceStatus.UNHEALTHY:
                    summary["unhealthy"] += 1
            return summary
