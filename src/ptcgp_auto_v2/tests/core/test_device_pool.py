# -*- coding: utf-8 -*-
"""
设备池单元测试
"""

from datetime import datetime, timedelta

from ptcgp_auto_v2.core.device_pool import DevicePool


def test_mark_available_sets_idle_time():
    """设备空闲时记录时间"""
    pool = DevicePool(["127.0.0.1:5555"])
    device = pool.get_device("127.0.0.1:5555")
    assert device is not None

    device.mark_available()
    assert device.became_idle_at is not None


def test_pick_idle_devices_for_shutdown_filters_by_time():
    """按空闲时长筛选需要关闭的设备"""
    pool = DevicePool(["127.0.0.1:5555", "127.0.0.1:5556"])
    device_a = pool.get_device("127.0.0.1:5555")
    device_b = pool.get_device("127.0.0.1:5556")
    assert device_a is not None
    assert device_b is not None

    now = datetime.now()
    device_a.mark_available()
    device_b.mark_available()
    device_a.became_idle_at = now - timedelta(seconds=200)
    device_b.became_idle_at = now - timedelta(seconds=50)

    picked = pool.pick_idle_devices_for_shutdown(2, min_idle_seconds=120)
    assert [device.address for device in picked] == ["127.0.0.1:5555"]


def test_add_and_remove_device():
    """设备池支持动态增删"""
    pool = DevicePool(["127.0.0.1:5555"])
    assert pool.add_device("127.0.0.1:5556") is True
    assert pool.add_device("127.0.0.1:5556") is False
    assert pool.remove_device("127.0.0.1:5556") is True
    assert pool.remove_device("127.0.0.1:5556") is False
